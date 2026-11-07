#!/bin/bash
# Create SR-IOV VFs on the Meteor Lake iGPU and hand them to xen-pciback.
# Usage: sudo ./sriov-vf-up.sh [num_vfs]
set -euo pipefail

PF=0000:00:02.0
PF_PATH=/sys/bus/pci/devices/$PF
NUM_VFS="${1:-3}"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root." >&2
    exit 1
fi

# Reset first: the kernel does not change a non-zero VF count directly.
echo 0 > "$PF_PATH/sriov_numvfs"
echo "$NUM_VFS" > "$PF_PATH/sriov_numvfs"

modprobe xen-pciback

for vf in "$PF_PATH"/virtfn*; do
    bdf=$(basename "$(readlink -f "$vf")")
    dev=/sys/bus/pci/devices/$bdf
    if [ -e "$dev/driver" ]; then
        echo "$bdf" > "$dev/driver/unbind"
    fi
    echo "$bdf" > /sys/bus/pci/drivers/pciback/new_slot
    echo "$bdf" > /sys/bus/pci/drivers/pciback/bind
done

lspci -nnk -s 00:02 | grep -E '^00:02|driver in use'
