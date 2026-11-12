# i915 SR-IOV on Qubes OS: findings

Status as of 2026-11-12. Setup steps are in [i915-sriov-build-notes.md](i915-sriov-build-notes.md). The browser investigation is in [webgl-firefox-findings.md](webgl-firefox-findings.md).

## Summary

- The vGPU works. A Linux HVM AppVM sees a VF, loads the custom i915, and renders on the Intel GPU.
- Rendering is limited by the Qubes window path. Offscreen GPU rendering is about 3.3x faster than windowed rendering.
- Browser WebGL is slow in Firefox but not in Chromium or Chrome. The cause is not yet found (see the browser findings file).
- With the external monitor at a scale above 1, the internal panel drops out once two or more VFs exist. With 0 or 1 VF, scaling works. Scale 1.0 works with 2 or more VFs.
- The kernel won't change the VF count while any VF is assigned.

## Setup (verified)

- dom0 kernel `7.2.11-1.qubes.fc41.x86_64`, with the custom i915 (strongtz/i915-sriov-dkms, tag 2026.11.05) in `extra/`.
- dom0 kernel options: `i915.enable_guc=3 i915.max_vfs=7 module_blacklist=xe`, set in `/etc/default/grub` and regenerated to `/boot/grub2/grub.cfg`.
- VM kernel `7.2.11-1.SRIOV`, built with `qubes-prepare-vm-kernel --include-devel`. Modules come from its `modules.img`.
- Test AppVM: HVM, 8 GB static memory (no swap seen), `software-rendering` service off in dom0.
- The guest sees the VF as `00:07.0`, bound to `i915` in SR-IOV VF mode.
- Guest kernel options: `module_blacklist=xe`. `i915.enable_guc` is not needed in the guest (tested).
- Guest GuC and HuC are `PRELOADED` from the host side. The VF does not load the Fedora firmware files, so the template does not need `intel-gpu-firmware`.
- The VF's display is disabled, as expected. Output stays on the PF in dom0.
- Rejected: `rd.qubes.hide_pci` with VF BDFs. The VFs don't exist at boot, and the attempt broke the boot. Hiding by vendor:device ID would also catch the PF (`8086:7d55`).

## Rendering results

Run in the guest, with `LIBGL_ALWAYS_SOFTWARE` set per test.

| Test | Result |
|---|---|
| `glxinfo -B`, GPU | Mesa Intel(R) Arc(tm) Graphics (MTL), direct rendering yes |
| `vainfo`, GPU | Intel iHD driver; VP8, VP9, AV1 decode and encode |
| glxgears, GPU / software | about 1900–2060 fps / 1120–1780 fps (too light to separate the two) |
| glmark2, GPU, windowed | 838 |
| glmark2, software, windowed | 305 |
| glmark2, GPU, offscreen | 2727 |

- Windowed GPU scores stay flat across scenes, while offscreen scores are about 3.3x higher. The Qubes window path is the limit.
- The offscreen run printed "Sync objects not supported, falling back to glFinish", and the software run printed "Failed to set swap interval". The ratio still holds.
- vCPU load was about 50% on the GPU run and about 90% on the software run.

## Display scaling with VFs

Setup: external 3440x1440 at scale 1.5, internal panel 2560x1600. Captures are `i915_display_info` with the external connected.

| VFs | Internal (pipe A) plane 1A | External (pipe B) |
|---|---|---|
| 0 | scaled framebuffer 5160x3760, visible | enabled, 3440x1440 |
| 1 | scaled framebuffer 5160x3760, visible | enabled, 3440x1440 |
| 2 | **hidden, no framebuffer** | enabled, 3440x1440 |
| 7 | **hidden, no framebuffer** | enabled, 3440x1440 |

The scaled framebuffer is 5160x3760 at 4 bytes per pixel, about 74 MiB.

GGTT layout, from `gt0/iov/ggtt_available` and `ggtt_provisioning`:

| VFs | Largest free range for the PF | Each VF |
|---|---|---|
| 0 | about 3.9 GiB | – |
| 1 | 16 MiB | VF1 about 3.9 GiB |
| 2 | 48 MiB | VF1 and VF2 about 2.0 GiB each |

What the source says (`gt/iov/intel_iov_provisioning.c`):

- Free GGTT is divided among the VFs (`pf_auto_provision_ggtt()`).
- The PF keeps a spare of at least 64 MiB (`pf_get_min_spare_ggtt()`, marked "preliminary"). The spare can be changed at runtime through the `ggtt_spare` attribute.
- Each VF range is placed at the top of the address space (`PIN_HIGH`).

Interpretation:

- With 2 or more VFs, the largest contiguous free range is below 74 MiB, so a new scaled framebuffer can't be allocated. This matches the hidden plane.
- With 1 VF, the largest free range is also below 74 MiB, but scaling works. The framebuffer was probably allocated before VF1 existed and survived. This is not confirmed yet.
- Scale 1.0 works with 2 VFs, because both framebuffers are small enough.

Ruled out:

- A CDCLK limit from the 7.3 `pixel_rate_cdclk` change. The logs show no atomic or CDCLK errors, and the failure depends on the VF count, which CDCLK does not.
- A change to the display limits in the port. The mode, dot-clock, and plane limits are identical to mainline 7.3.0.

## VF management

- `scripts/sriov-vf-up.sh` releases existing VFs before the reset, accepts a count from 0 to 7, and unbinds each new VF from `i915` before binding it to `pciback`.
- Hard constraint seen in practice: `Can't disable 3 VFs, 3 are still assigned`. The count can only change when every VF is unassigned.

## Planned, not implemented

- A VF pool, with one VF per VM, managed by a prep script (`vgpu-prep`) that attaches a free VF and sets the VM's preferences before start.
- A release script (`vgpu-release`) that detaches the VF and restores the preferences.
- `qvm-device` attachments as the source of truth for which VF is free.
- No pre-start hook for now. The first version runs the prep script by hand, followed by `qvm-start`.

Open questions for that design: pool size, the VM list, memory per VM, and whether the scaled-desktop limit should be checked by the script or only documented.

## Open items

1. Re-allocation test with 1 VF: does the scaled framebuffer survive a scale change? This decides whether 1 VF is stable.
2. `ggtt_spare` test: does raising the PF spare to about 128 MiB before creating 2 VFs keep enough contiguous room for the scaled framebuffer? Not started.
3. Verify the `qvm-device` attach and detach syntax for this Qubes version.
4. Confirm whether `intel_iommu=on` belongs in the dom0 kernel line or in `GRUB_CMDLINE_XEN_DEFAULT`.
5. Make `sriov-vf-up.sh` a systemd unit once the pool design is settled.

## Limits to live with

- Scaled desktop on the internal panel needs 0 or 1 VF, unless item 2 succeeds.
- Windowed 3D apps are limited by the Qubes window path. Games are out of scope.
- The VF count can't change while any VF is assigned.
- Each dom0 kernel update needs the module rebuilt and the VM kernel package rebuilt under a new name.
