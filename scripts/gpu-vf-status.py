#!/usr/bin/python3
#
# Copyright (C) 2026  Laszlo Zrubecz <mail@zrubi.hu>
#
"""Report each SR-IOV VF of the iGPU as free or in use. Read-only.

Usage: gpu-vf-status.py

Run in dom0, as the normal user.
"""

import glob
import os
import sys

import qubesadmin
import qubesadmin.exc

PF_BDF = "0000:00:02.0"
PF_PATH = f"/sys/bus/pci/devices/{PF_BDF}"


def read_sysfs(name):
    with open(f"{PF_PATH}/{name}", encoding="ascii") as f:
        return f.read().strip()


def vf_bdfs():
    links = glob.glob(f"{PF_PATH}/virtfn*")
    return sorted(os.path.basename(os.path.realpath(link)) for link in links)


def port_id_for(bdf):
    # 0000:00:02.1 -> 00_02.1, the DEVID part of BACKEND:DEVID
    return bdf[len("0000:"):].replace(":", "_")


def users_of(app, device):
    users = []
    for vm in app.domains:
        try:
            pci = vm.devices["pci"]
            for assignment in pci.get_assigned_devices():
                if assignment.matches(device):
                    users.append(f"{vm.name} (assigned)")
            for assignment in pci.get_attached_devices():
                if device in assignment.devices:
                    users.append(f"{vm.name} (attached)")
        except qubesadmin.exc.QubesException:
            continue
    return users


def main():
    app = qubesadmin.Qubes()
    exposed = {
        dev.port_id: dev
        for dev in app.domains["dom0"].devices["pci"].get_exposed_devices()
    }

    print(
        f"PF {PF_BDF}: sriov_totalvfs={read_sysfs('sriov_totalvfs')} "
        f"sriov_numvfs={read_sysfs('sriov_numvfs')}"
    )
    print(f"{'BDF':<14}{'BACKEND:DEVID':<16}{'STATE':<10}USED BY")

    free = 0
    for bdf in vf_bdfs():
        port = f"dom0:{port_id_for(bdf)}"
        device = exposed.get(port_id_for(bdf))
        if device is None:
            print(f"{bdf:<14}{port:<16}{'hidden':<10}not exposed to Qubes")
            continue
        users = users_of(app, device)
        if users:
            print(f"{bdf:<14}{port:<16}{'in use':<10}{', '.join(users)}")
        else:
            free += 1
            print(f"{bdf:<14}{port:<16}{'free':<10}")

    print(f"Free VFs: {free}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
