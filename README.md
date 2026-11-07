# nitropad-v56

Notes and configuration for the Nitropad V56 laptop (Meteor Lake iGPU) running Qubes OS.

## Contents

- `docs/i915-sriov-build-notes.md`: building and installing the out-of-tree i915 SR-IOV driver (`i915-sriov-dkms`) for dom0, with backup and revert steps.
- `scripts/sriov-vf-up.sh`: creates the SR-IOV VFs and binds them to `pciback` (run in dom0 after each boot).

## Quickstart

Read `docs/i915-sriov-build-notes.md` from the top. It lists the steps in order, and marks which commands run in the dev VM and which in dom0.

## Related repos

- `IaC/design`: design rules for the IaC repos.
- `IaC/inventory`: entry point and device index for the LAN.
