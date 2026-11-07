# i915 SR-IOV on Qubes OS: build notes

Goal: enable SR-IOV virtual GPUs (VFs) on a Meteor Lake iGPU (`8086:7d55`) in Qubes OS 4.3, and give Linux AppVMs access to them for rendering and video.

All steps apply to Qubes OS with a Xen-based dom0. Qubes terms are used throughout: dom0, qube, AppVM, template, VM kernel.

## Starting point

This work builds on the forum guide by spike-punk (https://forum.qubes-os.org/t/virtualised-intel-gpu-with-sr-iov/40649) and the out-of-tree driver by strongtz (https://github.com/strongtz/i915-sriov-dkms). The guide gave the basic idea. This document keeps what works and changes what was improved or clarified in this setup. Where the Qubes docs or source differ from the guide, the Qubes docs and source are followed.

Main differences from the guide:

- VFs are bound to `pciback` at runtime, not hidden at boot with `rd.qubes.hide_pci`.
- The guest uses a VM kernel package built with `qubes-prepare-vm-kernel`, not dom0 kernel modules.
- The software-rendering service is turned off in dom0, instead of being overridden in the guest.
- The GRUB config path is `/boot/grub2/grub.cfg`.

## Environment

- dom0 kernel: `7.2.11-1.qubes.fc41.x86_64` (`kernel-latest`)
- VM kernel for the test AppVM: `7.2.11-1.SRIOV` (built from the dom0 kernel)
- Dev VM: Fedora 43 qube, based on the same template as the test AppVMs. Used to build the driver.
- Boot: coreboot + Heads (Nitrokey); no UEFI Secure Boot
- Hardware: Meteor Lake iGPU (`8086:7d55`), Clevo-based laptop, single built-in display

## Scope

- Linux AppVMs using the vGPU for rendering and video, and the verification of that.
- Running games is out of scope. Rendering through the Qubes display path is limited (see Rendering tests), and that makes games not viable with this setup.

## Results

Verified on the Meteor Lake machine, dom0 `7.2.11-1.qubes.fc41.x86_64`.

- **dom0 driver:** the custom `i915.ko` loads on the PF (`00:02.0`) with `i915.enable_guc=3 i915.max_vfs=7 module_blacklist=xe`.
- **VFs:** 3 VFs created (`00:02.1`–`00:02.3`). The PF stays on `i915`. The VFs are bound to `pciback`.
- **Guest VF:** the test AppVM (HVM, VM kernel `7.2.11-1.SRIOV`) sees the VF as `00:07.0` and loads the custom `i915` with `Running in SR-IOV VF mode`.
- **GuC and HuC in the guest:** `PRELOADED`, provided by the host side. The guest does not load them from `/lib/firmware`. The guest kernel does not need `i915.enable_guc` (tested).
- **Display:** disabled for the VF (`Cannot read valid display IP version; disabling display`). Expected. Output stays on the PF in dom0.
- **OpenGL in the guest:** `LIBGL_ALWAYS_SOFTWARE=0 glxinfo -B` reports `Mesa Intel(R) Arc(tm) Graphics (MTL)`, direct rendering yes, Mesa 25.3.6.
- **Video in the guest:** `vainfo` loads the Intel iHD driver and lists VP8, VP9, and AV1 decode and encode.
- **Firefox:** WebRender is active on the Intel GPU. WebGL 1 and 2 report the Intel renderer. Hardware H.264 decode is listed as blocklisted, not investigated.

## Steps

1. **dom0 kernel options.** Set `GRUB_CMDLINE_LINUX_DEFAULT` for the dom0 kernel: `i915.enable_guc=3 i915.max_vfs=7 module_blacklist=xe`. Regenerate the config with `sudo grub2-mkconfig -o /boot/grub2/grub.cfg`. Regenerate the initramfs with `sudo dracut --regenerate-all --force`. Re-sign `/boot` with Heads.

2. **Copy the matching kernel headers from dom0 to the dev VM.** dom0 has no network, so the RPM is downloaded in dom0 and copied across. `--action=download` saves the requested packages to the current directory:
   ```
   # in dom0, from a working directory such as ~
   cd ~
   sudo qubes-dom0-update --action=download kernel-latest-devel-7.2.11-1.qubes.fc41
   ls kernel-latest-devel-*.rpm
   qvm-copy-to-vm <dev-vm> ~/kernel-latest-devel-7.2.11-1.qubes.fc41.x86_64.rpm
   ```
   ```
   # in the dev VM
   sudo dnf install ./kernel-latest-devel-7.2.11-1.qubes.fc41.x86_64.rpm
   ls /usr/src/kernels/7.2.11-1.qubes.fc41.x86_64
   ```
   The `ls` must show the headers. This replaces the earlier `qvm-run --pass-io` copy method.

3. **Install the build headers in dom0** (optional, needed for step 6 with `--include-devel`):
   ```
   sudo qubes-dom0-update qubes-kernel-vm-support kernel-devel
   ```

4. **Build the driver in the dev VM**, from tag `2026.11.05`, against the `7.2.11` headers from step 2:
   ```
   git clone --depth 1 --branch 2026.11.05 https://github.com/strongtz/i915-sriov-dkms.git
   cd i915-sriov-dkms
   make -C /usr/src/kernels/7.2.11-1.qubes.fc41.x86_64 M=$PWD modules
   ```
   Verify that `vermagic` matches dom0: `7.2.11-1.qubes.fc41.x86_64 SMP preempt mod_unload`.

5. **Copy the built modules to dom0 and install them** under `/lib/modules/7.2.11-1.qubes.fc41.x86_64/extra/`. Record the checksums in the dev VM first (`sha256sum` on `drivers/gpu/drm/i915/i915.ko` and `compat/intel_sriov_compat.ko`), then pull the files into dom0 with `qvm-run --pass-io <dev-vm> 'cat <path>' > <file>`, verify the checksums match, and install them. Run `depmod -a`, and check `modinfo -k 7.2.11-1.qubes.fc41.x86_64 -n i915` (it should point into `extra/`).

6. **Build the VM kernel package** in dom0 with `qubes-prepare-vm-kernel`, using a short display name:
   ```
   sudo qubes-prepare-vm-kernel --include-devel 7.2.11-1.qubes.fc41.x86_64 7.2.11-1.SRIOV
   ```
   `--include-devel` needs step 3. Drop the flag if you skip step 3. Check that `/var/lib/qubes/vm-kernels/7.2.11-1.SRIOV/` contains `vmlinuz`, `initramfs`, and `modules.img`, and that `modules.img` contains `extra/i915.ko`.

7. **Create the VFs** with `scripts/sriov-vf-up.sh` (in this repo): `sudo scripts/sriov-vf-up.sh <count>`. It resets `sriov_numvfs`, unbinds each VF from `i915`, and binds it to `pciback` with `new_slot` and `bind`. It must run after every boot until it is a systemd unit.

   Create only as many VFs as you need. Each VF's share of the GPU address space (GGTT), contexts, and doorbells is set when the VFs are created, by dividing the available amount by the number of VFs (`pf_auto_provision_ggtt()` and related functions in `gt/iov/intel_iov_provisioning.c`). Idle VFs use no RAM, but they do reduce the share the active VF gets. For this setup, one VF is enough. A test comparing 1 and 3 VFs is pending; update this note if it shows a difference.

8. **Configure the test AppVM** (dom0 only; the template is unchanged):
   ```
   qvm-prefs <appvm> virt_mode hvm
   qvm-prefs <appvm> kernel 7.2.11-1.SRIOV
   qvm-prefs <appvm> kernelopts "module_blacklist=xe"
   qvm-prefs <appvm> memory 8192
   qvm-service <appvm> software-rendering off
   ```

9. **Attach one VF** (`00:02.1`) to the AppVM with `qvm-device`. Record the exact command for your Qubes version (see Open items), then boot the AppVM.

10. **Check the guest:**
   - `lspci -nnk -s 00:07.0`: driver `i915`
   - `dmesg | grep -i i915`: `Running in SR-IOV VF mode`, GuC and HuC `PRELOADED`
   - `LIBGL_ALWAYS_SOFTWARE=0 glxinfo -B`: Intel Arc (MTL)
   - `LIBGL_ALWAYS_SOFTWARE=0 vainfo`: Intel iHD driver

**Qube RAM:** the test AppVM is set to 8 GB. No swap activity was seen, and the qube never used the full amount. A PCI-attached qube does not balloon memory (`qubes/vm/qubesvm.py`, `is_memory_balancing_possible()`), so the value set is the value used.

**Software rendering:** `LIBGL_ALWAYS_SOFTWARE=1` is set by `/etc/profile.d/qubes-gui.sh` in the guest, and only while the `software-rendering` service is enabled. The service is enabled by default (qvm-service man page). Turning it off in dom0 is the documented setting for a qube with a GPU. Overriding the variable per command only affects Mesa, not GTK or GDK.

## Rendering tests

Run in the guest, with nothing else open in the qube.

| Test | Command | Result |
|---|---|---|
| Renderer check | `LIBGL_ALWAYS_SOFTWARE=0 glxinfo -B` | Intel Arc (MTL), direct rendering yes |
| Video check | `LIBGL_ALWAYS_SOFTWARE=0 vainfo` | Intel iHD, VP8/VP9/AV1 decode and encode |
| glxgears, GPU | `vblank_mode=0 LIBGL_ALWAYS_SOFTWARE=0 timeout 30 glxgears` | ~1900–2060 fps |
| glxgears, software | `vblank_mode=0 LIBGL_ALWAYS_SOFTWARE=1 timeout 30 glxgears` | ~1120–1780 fps |
| glmark2, GPU, windowed | `vblank_mode=0 LIBGL_ALWAYS_SOFTWARE=0 glmark2` | **838** |
| glmark2, software, windowed | `vblank_mode=0 LIBGL_ALWAYS_SOFTWARE=1 glmark2` | **305** |
| glmark2, GPU, offscreen | `vblank_mode=0 LIBGL_ALWAYS_SOFTWARE=0 glmark2 --off-screen` | **2727** |
| WebGL in Firefox | browser on GPU | slow, similar to software (not measured) |

**Reading the results:**

- `glxgears` is too light to show the difference. It only shows that the GPU path works, since the CPU can keep up with its simple scene.
- `glmark2` shows the real gap: the GPU is about 2.7× faster than software in a window.
- Offscreen is about 3.3× faster than windowed, and windowed GPU scores stay flat across scenes. The limit is the Qubes window path: frames rendered on the GPU are read back to the CPU framebuffer that the GUI agent shares with dom0. The GPU has headroom.
- The offscreen run printed `Sync objects not supported, falling back to glFinish`, so its timing is slightly less precise. The gap is large enough that the conclusion holds.
- The software `glmark2` run printed `Failed to set swap interval`, so its numbers are less precise than the GPU run.
- vCPU load was about 50% on the GPU run and about 90% on the software run.

**Conclusion:** the GPU is in use and helps. The limit for windowed 3D apps, including Firefox WebGL, is the Qubes display path. Nothing in the VF or the driver removes it, and the only route around it needs a physical output on the GPU, which this laptop does not have.

**Display path source:** the Qubes dummy X driver (`xf86-video-dummy` in qubes-gui-agent-linux) keeps the framebuffer in normal memory by default (commit `9a04fad`, released in gui-agent-linux v4.3.7). The `DUMMY_GLAMOR_GNT_BACKED_FBBASE` define re-enables the grant-backed framebuffer. Not tested here.

## Open items

- **Xen options:** confirm whether `intel_iommu=on` is needed under Xen. The Xen-level IOMMU option is `iommu=` in `GRUB_CMDLINE_XEN_DEFAULT`. The current dom0 line keeps the option as it was tested.
- **VF persistence:** `sriov-vf-up.sh` must run after every boot until it becomes a systemd unit.
- **Each dom0 kernel update** needs the module rebuilt into `extra/` and the VM kernel package rebuilt under a new name. The module is tied to one kernel version.
- **`qvm-device` attach syntax** for this Qubes version: confirm and record the exact command.
- **Hardware H.264 decode** is blocklisted in Firefox's report. Not investigated.

## Fallbacks

- **Boot failure:** keep the previous Qubes kernel installed and select it in the GRUB menu, if the menu is shown.
- **System does not boot at all:** use the Heads emergency shell to correct the GRUB config so the OS can boot again. This happened during the `rd.qubes.hide_pci` attempt, which is why that option is listed under "Do not" below.
- **Heads refuses to boot** after `/boot` changes: enter the LUKS passphrase manually, then re-sign `/boot` with Heads.
- **Do not hide VFs with boot parameters.** `rd.qubes.hide_pci=` with BDFs that do not exist yet broke the boot. Hiding by vendor:device ID also catches the PF (`8086:7d55`).

To remove the setup: remove the options from `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`, regenerate `/boot/grub2/grub.cfg` and the initramfs, delete the module files from `extra/`, run `depmod`, delete the `7.2.11-1.SRIOV` VM kernel directory, and re-sign `/boot` with Heads.

## Risks

- Dom0 runs third-party kernel code.
- Kernel updates break the module until it is rebuilt.
- The driver is experimental.
- The `pciback` binding is done at runtime and must be repeated after every reboot until it is a systemd unit.
