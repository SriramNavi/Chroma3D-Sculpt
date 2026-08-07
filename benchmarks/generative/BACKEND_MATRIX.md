# CGB 0.1 Backend Matrix

Official sources were checked on 2026-08-07. Vendor claims are provenance, not benchmark results.

| ID | Benchmark pin | Inputs | Output/PBR | Open foundation | Default G0 state |
|---|---|---|---|---|---|
| `trellis2` | `microsoft/TRELLIS.2-4B` | image | GLB; base color, roughness, metallic, opacity | MIT weights/code/training entry point | `INSUFFICIENT_HARDWARE` |
| `hunyuan3d_2_1` | `Hunyuan3D-2.1` | image | GLB/OBJ; PBR paint | weights and training code; restrictive community license | `INSUFFICIENT_HARDWARE` |
| `tripo` | `v3.1-20260211` | text/image/multiview | textured/PBR; GLB/FBX evidence | no | `SPEND_NOT_AUTHORIZED` |
| `meshy` | `meshy-6` | text/image/multiview | GLB/OBJ/FBX/STL/USDZ/3MF; PBR | no | `SPEND_NOT_AUTHORIZED` |
| `rodin` | `Rodin Gen-2` | text/image/multiview | GLB/OBJ/FBX/STL/USDZ; PBR | no | `SPEND_NOT_AUTHORIZED` |
| `fake_generator` | `fake-generator-1.0` | test fixture | STL/OBJ, no texture | excluded from rankings | `READY_LOCAL` |

Official provenance:

- [Microsoft TRELLIS.2](https://github.com/microsoft/TRELLIS.2): 4B image-to-3D, PBR attributes, MIT, Linux-tested, 24 GB minimum NVIDIA VRAM, pretrained weights, and current `train.py`.
- [Tencent Hunyuan3D-2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1): full weights/training code, 10 GB shape, 21 GB texture, 29 GB combined, Windows/macOS/Linux statement, and PBR. Its [community license](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/main/LICENSE) has territory, scale, use, and disclosure restrictions requiring owner/legal review.
- [Tripo generation](https://platform.tripo3d.ai/docs/generation), [tasks](https://platform.tripo3d.ai/docs/task), and [billing](https://platform.tripo3d.ai/docs/billing): v3.1 exact pin, seed support, async task ID, output URL, and credit pricing. USD conversion remains `UNKNOWN`.
- [Meshy Image to 3D](https://docs.meshy.ai/en/api/image-to-3d), [Multi-Image](https://docs.meshy.ai/en/api/multi-image-to-3d), and [pricing](https://docs.meshy.ai/en/api/pricing): Meshy-6 exact pin, PBR maps, formats, task status, consumed credits, and deletion/cancellation surface. USD conversion remains `UNKNOWN`.
- [Hyper3D overview](https://developer.hyper3d.ai/api-specification/overview), [Gen-2](https://developer.hyper3d.ai/api-specification/rodin-generation-gen2), [status](https://developer.hyper3d.ai/api-specification/check-status), and [download](https://developer.hyper3d.ai/api-specification/download-results): asynchronous Gen-2 workflow and PBR outputs. Public Gen-2 USD cost was not bounded, so cost is `UNKNOWN`.

No version in this matrix is inferred from vendor marketing alone. A version that can no longer be verified must become `VERSION_UNVERIFIED` before execution.
