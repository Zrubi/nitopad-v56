# GPU disposables on Qubes OS 4.3

This is a proof of concept: disposables that each get one virtual function (VF) of an
SR-IOV capable GPU, and run one app with GPU access. It was tested on one system
(Meteor Lake-P iGPU, Qubes OS 4.3 dom0, out-of-tree `i915-sriov-dkms`). It is not a
Qubes OS change. The scripts are local tools that run in dom0.

## Components

| Script | Purpose |
|--------|---------|
| [`scripts/i915-vf.sh`](../scripts/i915-vf.sh) | Creates the VFs and binds them to `pciback`. Run as root in dom0. |
| [`scripts/gpu-vf-status.py`](../scripts/gpu-vf-status.py) | Read-only report of each VF as free or in use. |
| [`scripts/gpu-dispvm.py`](../scripts/gpu-dispvm.py) | Starts one app in a new disposable on a free VF. |

## Setup

1. **Create the VFs.** Follow [`i915-sriov-build-notes.md`](i915-sriov-build-notes.md),
   then run `sudo scripts/i915-vf.sh <count>` in dom0. The script must be run
   manually after every boot.

2. **Configure the disposable template** `vGPU-dvm` in dom0:

   ```
   qvm-prefs vGPU-dvm template_for_dispvms True
   qvm-prefs vGPU-dvm virt_mode hvm
   qvm-prefs vGPU-dvm kernel 7.2.11-1.SRIOV
   qvm-prefs vGPU-dvm kernelopts "module_blacklist=xe"
   qvm-prefs vGPU-dvm netvm ''
   qvm-prefs vGPU-dvm maxmem 0
   qvm-features vGPU-dvm preload-dispvm-max ''
   qvm-service vGPU-dvm software-rendering off
   ```

   - `kernelopts` is explained in [`i915-sriov-findings.md`](i915-sriov-findings.md).
   - `template_for_dispvms` is described in the official
     [disposable customisation](https://doc.qubes-os.org/en/r4.3/user/advanced-topics/disposable-customization.html)
     page.
   - `preload-dispvm-max` is the "Preload disposables" setting. It is described in
     [How to use disposables](https://doc.qubes-os.org/en/r4.3/user/how-to-guides/how-to-use-disposables.html#faster-disposable-startup-preloading).
     The launcher refuses to run if it is above 0.
   - `maxmem 0` is the "Include in memory balancing" setting, which is off. The same
     setting is used for PCI-attached qubes in
     [How to use PCI devices](https://doc.qubes-os.org/en/r4.3/user/how-to-guides/how-to-use-pci-devices.html).
   - `qvm-service` is the only way to set `software-rendering`. It is stored as a
     feature.

3. **Customise the disposable template** when needed. Starting `vGPU-dvm` to change its
   settings or applications is described in
   [Disposable customization](https://doc.qubes-os.org/en/r4.3/user/advanced-topics/disposable-customization.html#change-application-settings-manually).

4. **Copy the Python scripts to dom0**, for example to `~/bin/`, and make them
   executable.

## Usage

```
gpu-vf-status.py
gpu-dispvm.py [-v] [-q] vGPU-dvm <app-id>
```

- `<app-id>` is the desktop id, for example `org.gnome.Ptyxis` or `org.mozilla.firefox`.
  Short names such as `ptyxis` are not accepted.
- `-v` prints progress. `-q` reduces messages. The default is silent, as in `qvm-run`.
- The launcher returns the exit code of the app's service.

To find the id of an app:

```
grep -rh "StartApp+" ~/.local/share/applications/ /usr/share/applications/ | grep -i <name>
```

## Design

- **Launch:** the launcher uses the public `qubesadmin` API in separate steps: create
  the disposable, assign the VF, start the qube, run the app. These are the same calls
  that `qvm-run --dispvm` makes. Neither `qvm-run` nor Qubes core is changed.
- **Free VF:** a VF is free only if no qube has a persistent assignment and no qube has
  it attached. A VF held by any qube, running or halted, is never used. A static qube
  that owns a VF is therefore protected.
- **Lock:** `$XDG_RUNTIME_DIR/gpu-dispvm.lock`, held from the free-VF check until the VF
  is assigned.
- **Pool size:** the number of free VFs at launch time. The VF count is set by
  `i915-vf.sh`, up to `sriov_totalvfs` (7 on the tested system).
- **VF count changes:** only N → 0 → M, and only while no VF is in use. The VF-up script
  follows this order.
- **Static assignments:** they name an exact PCI ID. A qube with one starts only while
  that VF exists and is free.
- **Cleanup:** the disposable is removed when its app closes (`auto_cleanup`). The
  launcher also kills it if it is still running after its service ends. If assignment or
  start fails, the launcher removes the disposable, which returns the VF.

## Behaviour the launcher relies on

- Device state comes from the `qubesadmin` API. `get_assigned_devices()` gives the
  persistent assignments, and `get_attached_devices()` gives the live attachments
  (`qubesadmin/tools/qvm_device.py`).
- A VF has a `physfn` link in sysfs. A physical function does not.
- `DispVMWrapper.run_service` applies a longer connection timeout only before the
  disposable exists (`qubesadmin/vm/__init__.py`). The launcher passes
  `connect_timeout=disp.qrexec_timeout` itself.
- Disposables copy the template's cloneable properties and features, except
  `preload-dispvm*` (`qubes/vm/dispvm.py`, `DispVM.__init__`). This is how `kernel`,
  `kernelopts`, `virt_mode`, `maxmem`, and `service.software-rendering` reach the
  disposable.
- `from_appvm` requires `template_for_dispvms` to be set (`qubes/vm/dispvm.py`).
- `qvm-service` stores a service flag as the feature `service.<name>`
  (`qubesadmin/tools/qvm_service.py`).
- `qubes.StartApp+<id>` takes the desktop-file id. A short name fails with
  `<name> not found in <dirs>` and exit code 1. That message is shown with `qvm-run -p`.

## Upstream example

The official
[How to use disposables](https://doc.qubes-os.org/en/r4.3/user/how-to-guides/how-to-use-disposables.html#open-an-application-in-a-disposable-from-gui-domain)
page gives `qvm-run --dispvm=default-dvm --service -- qubes.StartApp+firefox` as the
command-line example. On the tested template, `firefox` is not an id. The id is
`org.mozilla.firefox`. This may depend on the template's packaging. It has not been
checked on a second template.

## Limitations

- **Desktop menu entries** are not covered. The dom0 menu runs each entry's `Exec` line
  verbatim. Those entries are generated from the disposable template's applications and
  rewritten after package changes in the template and on manual refresh, so any change
  to them has to be re-applied.
- **Hardware specifics:** the scripts use the PF address `0000:00:02.0` and the port
  format `dom0:00_02.x`. They are specific to this machine.
- **Leftovers:** a disposable left behind by a crash is removed by hand, using `qvm-ls`
  to find it and `qvm-remove` to delete it.
- **Boot:** `i915-vf.sh` must be run manually after each boot.
