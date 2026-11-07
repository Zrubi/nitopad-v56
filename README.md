# nitropad-v56

Notes and configuration for the Nitropad V56 laptop (Meteor Lake iGPU) running Qubes OS.

## Contents

- `docs/i915-sriov-build-notes.md`: building and installing the out-of-tree i915 SR-IOV driver (`i915-sriov-dkms`) for dom0, with backup and revert steps.
- `scripts/sriov-vf-up.sh`: creates the SR-IOV VFs and binds them to `pciback` (run in dom0 after each boot).

## Quickstart

Read `docs/i915-sriov-build-notes.md` from the top. It lists the steps in order, and marks which commands run in the dev VM and which in dom0.

## Related links

- Upstream bug reports (Dasharo):
  - https://github.com/Dasharo/dasharo-issues/issues/1617#issuecomment-6676778443
  - https://github.com/Dasharo/dasharo-issues/issues/1954
- Nitrokey support post: https://support.nitrokey.com/t/nitropad-v56-phantom-second-edp-in-the-vbt-gpu-hang-after-s3-resume/7809
- Qubes OS HCL report (Nitropad V56): https://forum.qubes-os.org/t/nitropad-v56-dasharo-heads-with-measured-boot/43877/2
