#!/usr/bin/python3
#
# Copyright (C) 2026  Laszlo Zrubecz <mail@zrubi.hu>
#
"""Start one app in a new GPU disposable on a free SR-IOV VF.

Usage: gpu-dispvm.py [-v] [-q] <disposable-template> <app-id>

-v prints progress, -q reduces messages. Errors are always printed.
"""

import argparse
import fcntl
import glob
import os
import subprocess
import sys

import qubesadmin
import qubesadmin.exc
from qubesadmin.device_protocol import DeviceAssignment
from qubesadmin.vm import DispVM

PF_BDF = "0000:00:02.0"
PF_PATH = f"/sys/bus/pci/devices/{PF_BDF}"
RUNTIME_DIR = os.environ.get("XDG_RUNTIME_DIR")
LOCK_PATH = os.path.join(RUNTIME_DIR or "", "gpu-dispvm.lock")


def say(verbose, level, msg):
    if verbose >= level:
        print(msg, file=sys.stderr)


def error(msg):
    print(msg, file=sys.stderr)


def vf_bdfs():
    links = glob.glob(f"{PF_PATH}/virtfn*")
    return sorted(os.path.basename(os.path.realpath(link)) for link in links)


def port_id_for(bdf):
    return bdf[len("0000:"):].replace(":", "_")


def users_of(app, device):
    users = []
    for vm in app.domains:
        try:
            pci = vm.devices["pci"]
            for assignment in pci.get_assigned_devices():
                if assignment.matches(device):
                    users.append(vm.name)
            for assignment in pci.get_attached_devices():
                if device in assignment.devices:
                    users.append(vm.name)
        except qubesadmin.exc.QubesException:
            continue
    return users


def free_vf(app):
    exposed = {
        dev.port_id: dev
        for dev in app.domains["dom0"].devices["pci"].get_exposed_devices()
    }
    for bdf in vf_bdfs():
        device = exposed.get(port_id_for(bdf))
        if device is not None and not users_of(app, device):
            return device
    return None


def remove_disposable(app, name):
    try:
        vm = app.domains[name]
        if vm.is_running():
            vm.kill()
        del app.domains[name]
    except (KeyError, qubesadmin.exc.QubesException):
        pass


def cleanup(app, name):
    try:
        vm = app.domains[name]
        if vm.is_running():
            vm.kill()
    except (KeyError, qubesadmin.exc.QubesException):
        pass


def create_and_assign(app, template, device):
    disp = DispVM.from_appvm(app, template).create_disposable()
    name = disp.name
    app.domains.clear_cache()
    try:
        vm = app.domains[name]
        vm.devices["pci"].assign(
            DeviceAssignment(device, mode="required", options={})
        )
        if not any(
            a.matches(device) for a in vm.devices["pci"].get_assigned_devices()
        ):
            raise qubesadmin.exc.QubesException("VF assignment not found")
    except Exception:
        remove_disposable(app, name)
        raise
    return disp, name


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="gpu-dispvm.py",
        description="Run one app in a GPU disposable.",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("-q", "--quiet", action="count", default=0)
    parser.add_argument("template")
    parser.add_argument("app")
    args = parser.parse_args(argv)
    args.verbose -= args.quiet
    return args


def main(argv):
    args = parse_args(argv)
    template, app_name, verbose = args.template, args.app, args.verbose

    if not RUNTIME_DIR:
        error("XDG_RUNTIME_DIR is not set. Log in normally first.")
        return 1

    app = qubesadmin.Qubes()
    if template not in app.domains:
        error(f"No such qube: {template}")
        return 1
    features = app.domains[template].features
    preload = int(features.get("preload-dispvm-max", 0) or 0)
    if preload > 0:
        error(f"{template} preloads disposables. Refusing.")
        return 1

    with open(LOCK_PATH, "w", encoding="ascii") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        device = free_vf(app)
        if device is None:
            error("No free GPU VF. Nothing started.")
            return 1
        try:
            disp, name = create_and_assign(app, template, device)
        except Exception as e:
            error(f"Could not prepare a disposable from {template}: {e}")
            return 1

    say(verbose, 1, f"Starting {app_name} in {name} with VF {device.port_id}")
    try:
        disp.start()
        proc = disp.run_service(
            f"qubes.StartApp+{app_name}",
            connect_timeout=disp.qrexec_timeout,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        error(f"Start failed in {name}: {e}")
        remove_disposable(app, name)
        return 1

    try:
        code = proc.wait()
    finally:
        cleanup(app, name)
    if code != 0:
        say(verbose, 1, f"{app_name} exited with code {code} in {name}")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
