# NitroPad v56

Notes and configuration for the Nitropad V56 laptop (Meteor Lake iGPU) running Qubes OS.

## Contents

- [`docs/i915-sriov-build-notes.md`](docs/i915-sriov-build-notes.md): building and installing the out-of-tree i915 SR-IOV driver (`i915-sriov-dkms`) for dom0, with backup and revert steps.
- [`docs/i915-sriov-findings.md`](docs/i915-sriov-findings.md): measured results, limits, and open items for the SR-IOV setup.
- [`docs/webgl-firefox-findings.md`](docs/webgl-firefox-findings.md): investigation of slow WebGL in Firefox on the vGPU AppVM.
- [`docs/gpu-dispvm-findings.md`](docs/gpu-dispvm-findings.md): GPU disposables built on the VFs: status, usage, design, and open items.
- [`scripts/i915-vf.sh`](scripts/i915-vf.sh): creates the SR-IOV VFs and binds them to `pciback` (run in dom0 after each boot).
- [`scripts/gpu-vf-status.py`](scripts/gpu-vf-status.py): read-only report of each VF as free or in use (dom0).
- [`scripts/gpu-dispvm.py`](scripts/gpu-dispvm.py): starts one app in a new GPU disposable on a free VF (dom0).


## Quickstart

Read [`docs/i915-sriov-build-notes.md`](docs/i915-sriov-build-notes.md) from the top. It lists the steps in order, and marks which commands run in the dev VM and which in dom0.

## Related links

- Driver source: [strongtz/i915-sriov-dkms](https://github.com/strongtz/i915-sriov-dkms), release [2026.11.05](https://github.com/strongtz/i915-sriov-dkms/releases/tag/2026.11.05) (the version used here)
- Upstream bug reports (Dasharo):
  - [Issue #1617: phantom eDP in the VBT](https://github.com/Dasharo/dasharo-issues/issues/1617#issuecomment-6676778443)
  - [Issue #1954: i915 GPU hang after S3 resume](https://github.com/Dasharo/dasharo-issues/issues/1954)
- [Nitrokey support post](https://support.nitrokey.com/t/nitropad-v56-phantom-second-edp-in-the-vbt-gpu-hang-after-s3-resume/7809)
- [Qubes OS HCL report](https://forum.qubes-os.org/t/nitropad-v56-dasharo-heads-with-measured-boot/43877)
