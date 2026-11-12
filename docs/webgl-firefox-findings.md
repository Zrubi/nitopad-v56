# WebGL in Firefox on the vGPU AppVM: findings

Status as of 2026-11-12. Part of the vGPU work; see [i915-sriov-findings.md](i915-sriov-findings.md) for the driver and display results, and [i915-sriov-build-notes.md](i915-sriov-build-notes.md) for setup.

## Problem

A WebGL page runs without errors in Chrome and Chromium on the vGPU AppVM, but is very slow in Firefox. Firefox with WebGL performs about the same as software rendering.

## What is confirmed

- The GPU is in use. Firefox's `about:support` reports WebRender on the Intel GPU (Mesa Intel(R) Arc(tm) Graphics (MTL), driver mesa/iris 25.3.6.0).
- WebGL 1 and WebGL 2 both report the Intel renderer, Mesa 25.3.6, OpenGL 4.6 core.
- The window protocol is X11, and the desktop is `x-qubes`.
- The Qubes virtual VGA (`0x1234:0x1111`) is inactive, as expected.
- `software-rendering` is off in dom0, so `LIBGL_ALWAYS_SOFTWARE` is not the cause.
- Windowed 3D apps are limited by the Qubes window path in general (glmark2: 838 windowed, 2727 offscreen, see the findings file).

## Blocked or unavailable features (Firefox)

| Feature | State | Reason reported |
|---|---|---|
| `DMABUF_SURFACE_EXPORT` | blocked | broken driver (`FEATURE_FAILURE_BROKEN_DRIVER`) |
| `MESA_THREADING` | failed | no glthread with EGL and X11 |
| `WEBRENDER_COMPOSITOR` | blocklisted | compositor disabled |
| `HARDWARE_VIDEO_DECODING_VULKAN` | user-disabled, blocklisted | preference |
| H.264 hardware decode | blocklisted | video decoding missing |
| H.264, HEVC, VP8/VP9 hardware encode | blocklisted | video encoding missing |
| `WEBGPU` | `navigator.gpu` is null | – |
| `WEBGPU_EXTERNAL_TEXTURE` | blocked | not supported on this OS |
| `VIDEO_HDR` | blocklisted | gfxInfo |

Available: `X11_EGL`, `DMABUF`, `HARDWARE_VIDEO_DECODING`, VP8, VP9, and AV1 hardware decode, `CANVAS_RENDERER_THREAD`, `ACCELERATED_CANVAS2D`.

## Leading candidate

`DMABUF_SURFACE_EXPORT` is blocked as a broken driver. That's the path that passes GPU frames to the compositor without a CPU copy. If it's off, each frame is copied, which would match the window-path limit measured with glmark2. This is not confirmed.

## Method

Compare two measurements only, so the comparison stays manageable:

1. One number per browser for the same page, with the same window size and no other tabs open. Use the page's own frame rate or timing.
2. One list per browser of GPU features that are blocked or fall back to software. In Firefox, search `about:support` for "blocklisted" and "failure code". In Chromium, use the "Problems Detected" section of `chrome://gpu`.

## Decisions

- Do not override Firefox's blocklist yet. Overrides can crash the browser, so review the source or documentation for each block first.
- Change one setting at a time, and check `about:support` after each change.

## Open items

1. Record the Chromium `chrome://gpu` report from the same AppVM, for comparison.
2. Save Firefox's `about:support` Media section, which covers video decode.
3. Measure the page in both browsers using the method above.
4. Check the Firefox source or documentation for the `DMABUF_SURFACE_EXPORT` block, and whether a preference can enable it safely.
5. Record the results here, and update the findings file if the window-path conclusion changes.

Games are out of scope for this project.
