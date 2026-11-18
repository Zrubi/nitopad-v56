# GPU disposables on Qubes OS 4.3: findings and usage

Status: working on this system. A GPU disposable is created from a disposable
template, given a free SR-IOV virtual function (VF) of the iGPU, and runs an app,
started from the dom0 CLI.

## Current status

- Status tool: `scripts/gpu-vf-status.py` (read-only). Working.
- VF-up tool: `scripts/sriov-vf-up.sh`. Working. Its order is tested and must not
  change without a new test.
- Launcher: `scripts/gpu-dispvm.py`. Working. Silent by default, `-v` for progress.
  It returns the app's exit code, and removes or kills the disposable when done.
- GPU settings: set once on the GPU disposable template. Disposables inherit them,
  including `kernelopts` and features such as `software-rendering off`.
- Apps tested: `org.gnome.Ptyxis` and `org.mozilla.firefox`, each on its own VF.
- Not done: desktop menu entries (see "Later").

## Deployment (dom0)

Copy the two Python scripts to dom0 (for example `~/bin/`) and make them executable.
`sriov-vf-up.sh` runs as root, after every boot, until it is a systemd unit.

## Usage

```
bin/gpu-dispvm.py [-v] [-q] <gpu-template> <app-id>
bin/gpu-vf-status.py
```

- `<gpu-template>`: the GPU disposable template you prepared (not `default-dvm`).
- `<app-id>`: the desktop id, for example `org.gnome.Ptyxis` or `org.mozilla.firefox`.
  Short names such as `ptyxis` are not accepted.
- Run the launcher as the normal user, without `sudo` and without `&`.
- It needs `XDG_RUNTIME_DIR`, which is set in a normal login session.

Find the id for an app with:

```
grep -rh "StartApp+" ~/.local/share/applications/ /usr/share/applications/ | grep -i <name>
```

## Design

- **Goal:** start a GPU-enabled disposable from the dom0 CLI, running a chosen app.
  Each GPU disposable gets one VF of the Meteor Lake iGPU (`00:02.x`).
- **No Qubes core change and no `qvm-run` change.** The launcher uses the public
  `qubesadmin` API, split into steps: create, assign the VF, start, run the app. These
  are the same calls `qvm-run --dispvm` makes (`qubesadmin/tools/qvm_run.py`,
  `qubesadmin/vm/__init__.py`).
- **VF selection:** a VF is free only if no qube has a persistent assignment or a live
  attachment for it. VFs assigned to any qube, running or halted, are never used. This
  protects static GPU qubes.
- **Lock:** `$XDG_RUNTIME_DIR/gpu-dispvm.lock`, held from the free-VF check until the
  VF is assigned.
- **Pool size** is dynamic: the number of free VFs at launch time. The VF-up tool sets
  how many VFs exist, up to `sriov_totalvfs` (7 on this system).
- **VF count** can only change as N → 0 → M, and only when no VF is in use. The VF-up
  tool follows this.
- **Static assignments** are by exact PCI ID. A qube with one starts only if that VF is
  present and free.
- **Cleanup:** the disposable is removed when its app closes (`auto_cleanup`). The
  launcher also kills it if it is still running after its service ends, as
  `DispVMWrapper.cleanup()` does. If assignment or start fails, the launcher removes
  the disposable, which returns the VF.
- **Output:** silent by default, as in `qvm-run`. Verbosity is `-v` count minus `-q`
  count. The terminal check in `qvm-run` only controls escape-character filtering, so
  the launcher doesn't use it.
- **Preloading** must be off on the GPU disposable template. The launcher refuses
  otherwise.

## Verified facts

- `qvm-pci` without arguments shows only live attachments. Use `qvm-pci ls -s
  --with-sbdf` to include persistent assignments.
- Each device appears as a row for its persistent assignment (`*<qube> (required)`)
  and a row for its live attachment (`<qube> (attached)`). Match rows on
  `BACKEND:DEVID` (for example `dom0:00_02.1`), not on SBDF.
- A VF has a `physfn` link in sysfs; the PF has none.
- `DispVMWrapper.run_service` applies a longer connection timeout only before the
  disposable is created, so the launcher passes `connect_timeout=disp.qrexec_timeout`
  itself.
- Disposable settings: cloneable properties and features (except `preload-dispvm*`)
  are copied from the disposable template (`qubes/vm/dispvm.py`, lines 378–405).
- `qubes.StartApp+<id>` requires the desktop-file id. A short name returns
  `<name> not found in <dirs>` with exit code 1. That message is hidden unless `-p`
  (`--pass-io`) is used.
- Ids depend on the template. On the tested GPU template, Firefox is
  `org.mozilla.firefox`, and Ptyxis is `org.gnome.Ptyxis`. The short names `firefox`
  and `ptyxis` are not ids there.
- The `core-agent-linux` source is checked out at tag `v4.3.48`. The tag verifies with
  the builder's own method: a separate keyring, the Qubes developer keys, and the Qubes
  Master Signing Key trusted, then `git verify-tag`.

## Upstream documentation note

- The "How to use disposables" page gives
  `qvm-run --dispvm=default-dvm --service -- qubes.StartApp+firefox` as the CLI example.
  On the tested template, `firefox` is not an id, and the working id is
  `org.mozilla.firefox`. Whether the example is wrong in general depends on the template
  packaging, which has not been checked on a second template.

## Later

- **Desktop integration:** the menu runs a desktop entry's `Exec` verbatim, so the GPU
  path needs its own entries. The options are generated `.desktop` files that call the
  launcher, or a generic upstream hook. Menu entries are regenerated after template
  package changes and on manual refresh, so patched entries must be re-applied.
- **Security:** the launcher runs as root in dom0 (trusted computing base). Keep it
  small, and never touch a VF assigned to any qube. GPU disposables share userland with
  normal disposables, so use them for GPU tasks only. The out-of-tree `i915-sriov-dkms`
  module is an existing risk.
- **Hardware specifics:** the launcher and status tool use the PF address `0000:00:02.0`
  and the port format `dom0:00_02.x`. These are specific to this machine.
