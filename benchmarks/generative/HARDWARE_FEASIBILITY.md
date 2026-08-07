# G0 Hardware Feasibility

Local read-only inventory on 2026-08-07:

| Component | Detected |
|---|---|
| OS | Windows 11 Home Single Language, 10.0.26200 |
| CPU | Intel Core i7-13620H, 16 logical processors |
| RAM | 33,963,319,296 bytes |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU |
| VRAM | 8,188 MiB from `nvidia-smi` |
| NVIDIA driver / reported CUDA | 581.80 / 13.0 |
| System Python | 3.13.5 |
| Blender | 4.4.3 at the repository's established external tool path `D:\Softwares\Design\Blender\blender.exe` (validated during G0 acceptance) |

| Open model | Official requirement | Classification | Reason |
|---|---|---|---|
| TRELLIS.2-4B | Linux tested; NVIDIA GPU with at least 24 GB; CUDA 12.4 recommended | `LOCAL_NOT_FEASIBLE` / `CLOUD_RECOMMENDED` | Windows plus 8 GB VRAM is below the documented minimum. |
| Hunyuan3D-2.1 shape | 10 GB VRAM | `LOCAL_NOT_FEASIBLE` | 8 GB VRAM is below the documented shape requirement. |
| Hunyuan3D-2.1 shape+texture | 29 GB total | `LOCAL_NOT_FEASIBLE` / `CLOUD_RECOMMENDED` | 8 GB VRAM is far below the documented full pipeline requirement. |

No checkpoint, runtime package, or model weight was downloaded to reach these classifications. CPU inference is not silently enabled. Cloud provisioning remains disabled.
