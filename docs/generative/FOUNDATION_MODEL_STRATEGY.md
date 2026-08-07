# Foundation Model Strategy

G0 does not train, fine-tune, download weights, acquire training data, or provision compute.

## TRELLIS.2-4B

- Weights/code: published by Microsoft; MIT.
- Representation: O-Voxel field-free sparse voxel structure with a 3D VAE and diffusion transformer.
- Conditioning/output: image-to-3D, arbitrary topology, PBR surface attributes, GLB export.
- Training path: repository contains `train.py` and data toolkit; exact Chroma3D fine-tuning feasibility remains unexecuted.
- Infrastructure class: Linux NVIDIA, at least 24 GB VRAM for documented inference; training requires materially larger multi-GPU infrastructure.
- G0 disposition: strong research candidate on paper, but local execution is not feasible and no benchmark winner can be inferred.

## Hunyuan3D-2.1

- Weights/training: full model weights and training code are officially published.
- Representation: separate 3.3B image-to-shape and 2B PBR paint components.
- Conditioning/output: image-conditioned shape plus physics-grounded PBR texture synthesis.
- Fine-tuning path: officially positioned for fine-tuning/extension; actual recipes/data/compute remain unvalidated by G0.
- Infrastructure class: 10 GB shape, 21 GB texture, 29 GB combined official VRAM figures.
- License: Tencent community license; territory, scale, disclosure, and use restrictions require explicit legal/product review before foundation selection.
- G0 disposition: technically attractive for future proprietary-model work, but locally infeasible and license-sensitive.

## Decision rule

Foundation choice requires genuine CGB Smoke3 and Core10 results plus license, fine-tuning, infrastructure, and data-governance review. Documentation alone cannot produce `BEST_OPEN_RESEARCH_FOUNDATION`.
