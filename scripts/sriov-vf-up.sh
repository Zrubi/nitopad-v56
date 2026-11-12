#!/bin/bash
# Create SR-IOV VFs on the Meteor Lake iGPU and hand them to xen-pciback.
# Usage: sudo ./sriov-vf-up.sh [0-7]   (0 removes all VFs, default 3)
set -euo pipefail

PF=0000:00:02.0
PF_PATH=/sys/bus/pci/devices/$PF
NUM_VFS="${1:-3}"

if ! [[ "$NUM_VFS" =~ ^[0-9]+$ ]] || [ "$NUM_VFS" -gt 7 ]; then
    echo "Usage: $0 [0-7]   (0 removes all VFs)" >&2
    exit 2
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root." >&2
    exit 1
fi

# The kernel refuses to change the VF count while any VF is still bound to a
# driver (pciback counts as assigned), so release every existing VF first.
for vf in "$PF_PATH"/virtfn*; do
    [ -e "$vf" ] || continue
    bdf=$(basename "$(readlink -f "$vf")")
    dev=/sys/bus/pci/devices/$bdf
    if [ -e "$dev/driver" ]; then
        echo "$bdf" > "$dev/driver/unbind"
    fi
done

if ! echo 0 > "$PF_PATH/sriov_numvfs"; then
    echo "Could not remove VFs. A qube may still have one attached." >&2
    exit 1
fi

if [ "$NUM_VFS" -eq 0 ]; then
    echo "VFs removed."
    exit 0
fi

echo "$NUM_VFS" > "$PF_PATH/sriov_numvfs"

modprobe xen-pciback

for vf in "$PF_PATH"/virtfn*; do
    bdf=$(basename "$(readlink -f "$vf")")
    dev=/sys/bus/pci/devices/$bdf
    # i915 probes new VFs on creation; release them before pciback can bind.
    if [ -e "$dev/driver" ]; then
        echo "$bdf" > "$dev/driver/unbind"
    fi
    echo "$bdf" > /sys/bus/pci/drivers/pciback/remove_slot 2>/dev/null || true
    echo "$bdf" > /sys/bus/pci/drivers/pciback/new_slot
    echo "$bdf" > /sys/bus/pci/drivers/pciback/bind
done

lspci -nnk -s 00:02 | grep -E '^00:02|driver in use'
