# diffusion models for video generation

*effort standard · pool 416 · landmarks 80 · schema ['model_architecture', 'temporal_modeling', 'conditioning_method', 'training_regime', 'resolution_approach', 'key_innovation'] · grounded 23 · off-digest 2*

---

# Literature Review: Diffusion Models for Video Generation

The evolution of video generation has transitioned from early attempts at disentangling scene dynamics using Generative Adversarial Networks (GANs) to the current frontier of massive-scale Latent Diffusion Models (LDMs) and Diffusion Transformers (DiTs). This review traces that development from foundational datasets and generative principles to the sophisticated spatio-temporal diffusion architectures of today.

## Origins: Foundational Generative Principles and Video Datasets (2012–2016)

The journey toward automated video synthesis began with the establishment of large-scale benchmarks, most notably the **UCF101** dataset, which provided over 13k clips of unconstrained human action classes (arXiv:1212.0402). Early generative research focused on two distinct paths: variational inference and adversarial learning.

In the realm of variational models, the reparameterization trick introduced in **arXiv:1312.6114** enabled efficient optimization of continuous latent variables, a principle that would later underpin diffusion processes. This was followed by the introduction of a generative model inspired by non-equilibrium statistical physics (arXiv:1503.03585), which utilized an iterative forward diffusion process to destroy structure and a learned reverse process to restore it—the fundamental mechanism of modern diffusion models.

Simultaneously, video-specific generation was explored through GANs. **arXiv:1609.02612** introduced a spatio-temporal convolutional GAN designed to untangle a scene's foreground from its background. This was extended by **arXiv:1611.06624**, which utilized a two-generator architecture (temporal and image generators) and singular value clipping to stabilize the training of temporal and image generation.

## Key Advances: From GAN Decomposition to Diffusion Foundations (2017–2020)

As the field matured, researchers sought more controllable and stable architectures. A significant breakthrough in video control was **MoCoGAN** (arXiv:1707.04993), which decomposed video generation into separate, controllable content and motion latent spaces using a stochastic process.

The period between 2017 and 2020 saw the rise of architectures that would eventually dominate the diffusion landscape:
*   **Transformers:** The introduction of the Transformer architecture (arXiv:1706.03762), which dispensed with recurrence and convolutions in favor of attention mechanisms, provided the scaling backbone for later models.
*   **Discrete Representations:** **VQ-VAE** (arXiv:1711.00937) introduced vector quantization to learn discrete latent representations, a method critical for scaling generative modeling to high-resolution video.
*   **Diffusion Breakthroughs:** The field underwent a paradigm shift with **Denoising Diffusion Probabilistic Models (DDPMs)** (arXiv:2006.11239), which established a connection between diffusion models and denoising score matching. This was further refined by **arXiv:2010.02502**, which introduced non-Markovian diffusion processes to allow for 10x to 50x faster sampling. Finally, **arXiv:2011.13456** unified score-based and diffusion models into a single Stochastic Differential Equation (SDE) framework, enabling high-fidelity generation at 1024 x 1024 resolutions.

## Current Frontier: Latent Diffusion and Spatio-Temporal Scaling (2021–2024)

The current era is defined by the application of diffusion models to the latent space of pretrained autoencoders, significantly reducing computational complexity while preserving detail.

### Latent and Text-to-Video Diffusion
**Latent Diffusion Models (LDMs)** (arXiv:2112.10752) revolutionized the field by operating in the latent space of pretrained autoencoders and using cross-attention for flexible conditioning. This paved the way for specialized video models:
*   **Make-A-Video** (arXiv:2209.14792) successfully translated text-to-image progress to video by decoupling visual/multimodal learning from motion learning, avoiding the need for paired text-video data.
*   **Video Diffusion Models (VDM)** (arXiv:2204.03458) introduced joint training from image and video data to improve quality.
*   **Imagen Video** (arXiv:2210.02302) utilized a cascade of video diffusion models with interleaved spatial and temporal super-resolution.

### Advanced Temporal Modeling and Control
Modern models have moved beyond simple frame concatenation toward sophisticated temporal mechanisms:
*   **Control and Editing:** **ControlNet** (arXiv:2302.05543) introduced "zero convolutions" to add spatial conditioning (e.g., depth, pose) to pretrained models. For editing, **Text2Video-Zero** (arXiv:2303.13439) enables zero-shot generation by repurposing text-to-image models through motion-enriched latent codes.
*   **Long-Form Video:** To address temporal consistency, **Latent Video Diffusion Models** (arXiv:2211.13221) leveraged hierarchical diffusion in a 3D latent space to generate videos exceeding 1,000 frames. **FreeNoise** (arXiv:2310.15169) offered a tuning-free approach by rescheduling noise sequences for long-range correlation.
*   **Scaling with Transformers:** The architecture has shifted from U-Nets to **Diffusion Transformers (DiTs)** (arXiv:2212.9748), which replace the U-Net backbone with a transformer operating on latent patches to improve scalability. The most recent frontier includes **CogVideoX** (arXiv:2408.06072), which utilizes an expert transformer with adaptive LayerNorm for deep modality fusion, and **HunyuanVideo** (arXiv:2412.03603), a massive 13-billion-parameter open-source foundation model.

## Tensions and Open Problems

The literature reveals several ongoing tensions in the field:
1.  **Data Requirements:** There is a tension between models requiring massive paired text-video datasets and those attempting to leverage unpaired data or text-image pairs (e.g., **Make-A-Video** vs. **CogVideo**).
2.  **Complexity vs. Efficiency:** While cascaded models (e.g., **LAVIE**, arXiv:2309.15103) achieve high resolution through super-resolution stages, they face competition from more efficient 3D U-Net designs like **MagicVideo** (arXiv:2211.11018).
3.  **Evaluation Standards:** As models become more capable, the need for rigorous benchmarking is highlighted by the introduction of **VBench** (arXiv:2311.17982), which critiques existing metrics by dissecting video quality into 16 disentangled dimensions.