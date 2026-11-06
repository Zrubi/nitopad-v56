# i915 SR-IOV build notes

Goal: enable SR-IOV virtual GPUs on a Nitropad V56 (Meteor Lake iGPU) in Qubes OS, using the out-of-tree i915 driver from https://github.com/strongtz/i915-sriov-dkms. Follows the forum guide: https://forum.qubes-os.org/t/virtualised-intel-gpu-with-sr-iov/40649

## Environment

- dom0 kernel: `7.2.11-1.qubes.fc41.x86_64` (`kernel-latest` package)
- Dev VM: Fedora 43, with `kernel-latest-devel-7.2.11-1.qubes.fc41` installed for the matching headers
- Boot: coreboot + Heads (Nitrokey); no UEFI Secure Boot

## Steps so far

1. Read the Qubes forum guide and the driver README.
2. Chose to build the module in a dev VM rather than in dom0, to keep dom0 minimal. This replaces the forum's `dkms add` / `dkms install` in dom0.
3. Got the matching headers into the dev VM:
   - dom0 has no network, and `dnf download` doesn't work there.
   - Ran `sudo qubes-dom0-update --action=download kernel-latest-devel-7.2.11-1.qubes.fc41` in dom0 to fetch the RPM.
   - Copied it to the dev VM and installed it with `sudo dnf install ./<rpm>`.
4. Checked the driver's build files:
   - `dkms.conf`: `BUILD_EXCLUSIVE_KERNEL` accepts 7.2.x.
   - `Makefile`: the module was ported from mainline 7.3.0.
5. Built the modules in the dev VM, against the installed headers, from the `2026.11.05` tag:

   ```
   git clone --depth 1 --branch 2026.11.05 https://github.com/strongtz/i915-sriov-dkms.git
   cd i915-sriov-dkms
   make -C /usr/src/kernels/7.2.11-1.qubes.fc41.x86_64 M=$PWD modules
   ```

   Build succeeded. Output: `i915.ko`, `intel_sriov_compat.ko`, `kvmgt.ko`, `xe.ko`.
6. Verified the build:
   - `vermagic` is `7.2.11-1.qubes.fc41.x86_64 SMP preempt mod_unload`, which matches dom0.
   - `CONFIG_MODULE_SIG_FORCE` is not set, so unsigned modules will load (the kernel will be tainted).
   - Warnings: the kernel was built with GCC 14.3.1 and the build used GCC 15.3.1. The pahole version also differs, so the module has no BTF.

## Compiled modules

- `i915-sriov-dkms/drivers/gpu/drm/i915/i915.ko`: needed for SR-IOV
- `i915-sriov-dkms/compat/intel_sriov_compat.ko`: may be needed
- `i915-sriov-dkms/drivers/gpu/drm/i915/kvmgt.ko`: GVT-g, not needed for SR-IOV
- `i915-sriov-dkms/drivers/gpu/drm/xe/xe.ko`: not needed (xe is blacklisted)

## Next steps (up to reboot)

Replace `<dev-vm>` with the dev VM's name. The dev VM must be running for the copy in step A.

### A. Copy the modules to dom0

In the dev VM, record the checksums:

```
sha256sum /home/user/Documents/QubesOS/i915-sriov-dkms/drivers/gpu/drm/i915/i915.ko /home/user/Documents/QubesOS/i915-sriov-dkms/compat/intel_sriov_compat.ko
```

In dom0, pull the files out of the dev VM (the method the forum guide uses):

```
mkdir -p ~/i915-sriov
qvm-run --pass-io <dev-vm> 'cat /home/user/Documents/QubesOS/i915-sriov-dkms/drivers/gpu/drm/i915/i915.ko' > ~/i915-sriov/i915.ko
qvm-run --pass-io <dev-vm> 'cat /home/user/Documents/QubesOS/i915-sriov-dkms/compat/intel_sriov_compat.ko' > ~/i915-sriov/intel_sriov_compat.ko
sha256sum ~/i915-sriov/*.ko
```

The two checksums in dom0 must match the dev VM's. If they don't, don't install anything.

### B. Check and install the modules (dom0)

Check the vermagic first:

```
modinfo ~/i915-sriov/i915.ko | grep vermagic
```

It must read `7.2.11-1.qubes.fc41.x86_64`. Then install them:

```
sudo mkdir -p /lib/modules/7.2.11-1.qubes.fc41.x86_64/extra
sudo install -m 644 ~/i915-sriov/i915.ko ~/i915-sriov/intel_sriov_compat.ko /lib/modules/7.2.11-1.qubes.fc41.x86_64/extra/
sudo depmod -a 7.2.11-1.qubes.fc41.x86_64
modinfo -k 7.2.11-1.qubes.fc41.x86_64 -n i915
```

The last command should print the path under `extra/`.

### C. Set the kernel options and rebuild the initramfs (dom0)

Edit the GRUB defaults. The forum has a typo (`/etc/defualt/grub`); the correct file is `/etc/default/grub`:

```
sudo vim /etc/default/grub
```

Add these to the `GRUB_CMDLINE_LINUX_DEFAULT` line:

```
intel_iommu=on i915.enable_guc=3 i915.max_vfs=7 module_blacklist=xe
```

Then regenerate the config and the initramfs:

```
sudo grub2-mkconfig -o /boot/efi/EFI/qubes/grub.cfg
sudo dracut --regenerate-all --force
```

Heads must be re-signed after this step, because `/boot` has changed. Details to follow.

### D. Reboot and check the driver (dom0)

```
sudo reboot
```

After boot:

```
cat /proc/cmdline
lsmod | grep -E '^i915|intel_sriov_compat'
dmesg | grep -i -E 'i915|taint'
```

The command line should contain the options from step C. `i915` should be loaded. A "tainted" message is expected for an out-of-tree module.

## If it doesn't boot, or the driver misbehaves

Keep an older Qubes kernel installed so you can boot it. Older kernels don't use the new module, so choosing one at the GRUB menu bypasses it.

Other fallbacks at boot:

- **Keep the new kernel but skip the driver:** press `e` on the GRUB entry and append `module_blacklist=i915,xe`. Dom0 may fall back to a basic framebuffer, so the screen can look different, but the system should still boot.
- **Heads refuses to boot** because `/boot` changed: enter the LUKS passphrase manually, then re-sign `/boot` with Heads. Heads' exact prompts depend on its version.

To undo the changes from dom0, booted on an older kernel or with the blacklist option:

1. Remove the options from the `GRUB_CMDLINE_LINUX_DEFAULT` line in `/etc/default/grub` (`sudo vim /etc/default/grub`).
2. Regenerate GRUB and the initramfs: `sudo grub2-mkconfig -o /boot/efi/EFI/qubes/grub.cfg` and `sudo dracut --regenerate-all --force`.
3. Remove the installed modules and refresh the module index:

   ```
   sudo rm -f /lib/modules/7.2.11-1.qubes.fc41.x86_64/extra/i915.ko /lib/modules/7.2.11-1.qubes.fc41.x86_64/extra/intel_sriov_compat.ko
   sudo depmod -a 7.2.11-1.qubes.fc41.x86_64
   ```

4. Re-sign `/boot` with Heads and reboot.

## Later (not in this session)

- Create the virtual GPUs and attach them to qubes.
- Prepare the qubes (HVM mode, kernel, kernel options, software rendering).
- Verify acceleration inside a qube.
- Re-sign `/boot` with Heads after any kernel or module change.

## Risks

- Dom0 runs third-party kernel code.
- Kernel updates break the module until it is rebuilt.
- The forum reports display hangs in some games.
