*deep research · 3 round(s) · 200 landmarks · frontier≥2024: 51 · 4 full-PDF critiques · grounded 43 · off-digest 0*

# From Waveforms to Latents: The Evolution of Neural Audio Compression

The fundamental challenge of audio compression lies in the persistent tension between bit-rate economy and perceptual fidelity. Traditional psychoacoustic codecs, while highly optimized for standard playback, often struggle to maintain the complex textures of music or the nuanced prosody of speech when operating under extreme bandwidth constraints. The emergence of neural audio codecs has revolutionized this landscape by replacing rigid, hand-crafted signal-processing heuristics with learned latent representations. This shift is critical for the next generation of digital communication, as it enables the high-fidelity streaming of diverse acoustic content and the ultra-low-latency synthesis required for seamless, real-time human-machine interaction.

This review traces the developmental trajectory of the field, beginning with the *Foundations of Neural Audio Generation and Early Speech Coding* [van den Oord et al., 2016] that established the potential for deep generative models to capture complex acoustic distributions. We then examine the methodological breakthroughs found in *Advances in Vector Quantization and Residual Codec Architectures* [van den Oord et al., 2017], which provided the framework for discretizing continuous audio into efficient, compressed codebooks. The narrative progresses to the practical constraints of deployment, specifically *Streaming, Low-Latency, and Real-Time Communication Codecs* [Défossez et al., 2022], addressing the temporal requirements of live digital environments. We further explore the recent paradigm shift of *Bridging Codecs with Language Modeling and Generative Synthesis* [Borsos et al., 2023], where compressed audio tokens are increasingly treated as linguistic units for large-scale modeling. After addressing the critical need for *Evaluation, Robustness, and Interpretability of Neural Codecs* [Author, Year], we conclude by surveying the research *Frontier: High-Fidelity, Universal, and Sparse Quantization* [Author, Year], where the focus lies in achieving seamless, high-resolution audio across all domains and acoustic environments.

## Foundations of Neural Audio Generation and Early Speech Coding

The transition from traditional signal processing to neural audio modeling began with the development of autoregressive architectures capable of modeling raw waveforms. WaveNet [arXiv:1609.03499] established a foundational approach by modeling joint probabilities over raw audio samples as a product of conditional distributions. While highly effective for both speech and music, its fully probabilistic autoregressive nature presents significant computational demands. In contrast, SampleRNN [arXiv:1612.07837] addressed the need to capture correlations across varying temporal scales by employing a hierarchical density model. By combining autoregressive multilayer perceptrons with stateful recurrent neural networks (such as GRUs or LSTMs) operating at different temporal resolutions, SampleRNN provided a more structured method for modeling speech and human vocal sounds than the single-scale approach of WaveNet [arXiv:1609.03499, arXiv:1612.07837].

A significant shift in the field occurred with the move from continuous latent spaces to discrete representations. The Vector Quantised-Variational AutoEncoder (VQ-VAE) [arXiv:1711.00937] introduced vector quantization (VQ) to replace continuous latent variables with discrete codes, utilizing a learned prior to improve sample coherence. This innovation provided a critical bridge between generative modeling and efficient representation learning, influencing subsequent work in speech and video generation [arXiv:1711.00937].

These generative advancements were quickly adapted for speech coding tasks. Early efforts focused on using WaveNet as a decoder, where the model reconstructed high-quality speech from bitstreams provided by conventional parametric encoders, achieving a bitrate efficiency of 2.4 kb/s [arXiv:1712.01120]. However, the high complexity of pure autoregressive models necessitated more efficient architectures. LPCNet [arXiv:1810.11846] addressed this by integrating linear prediction with recurrent neural networks (GRUs), effectively reducing model complexity while maintaining quality in speaker-independent synthesis [arXiv:1810.11846]. This trend toward efficiency was furthered by the Cascaded Cross-Module Residual Learning (CMRL) framework [arXiv:1906.07769], which utilized a pipeline of bottleneck residual learning and soft-to-hard quantization. By designing each module to reconstruct the residual from its predecessor, CMRL achieved a lightweight profile of only 0.9 million parameters while maintaining competitive subjective quality in MUSHRA tests [arXiv:1906.07769].

While these developments focused on architectural efficiency and discretization, the field also began to investigate the fundamental limits of model performance. The study of neural scaling laws [arXiv:2102.06701] provided a theoretical framework to explain how test loss scales with model parameters and dataset size. By identifying four distinct scaling regimes—variance-limited and resolution-limited for both dataset and model size—this work offered a systematic way to inform whether increasing model scale would yield diminishing returns in audio modeling tasks [arXiv:2102.06701].

## Advances in Vector Quantization and Residual Codec Architectures

The evolution of neural audio codecs has been largely defined by refinements to Residual Vector Quantization (RVQ) to balance bitrate efficiency with high-fidelity reconstruction. Early foundational work, such as SoundStream (arXiv:2107.03312), established a fully convolutional encoder-decoder framework utilizing RVQ and adversarial/reconstruction losses to support streamable, low-latency inference across speech and music. This architecture laid the groundwork for subsequent high-fidelity models, though later research has focused on overcoming specific limitations in quantization efficiency and artifact reduction.

A significant leap in fidelity was achieved by introducing multiscale spectrogram adversaries. For instance, arXiv:2210.13438 utilized a single multiscale spectrogram adversary and a novel gradient "loss balancer" to decouple hyper-parameter weights from loss scales, achieving state-of-the-art MUSHRA scores. Notably, this model outperformed Lyra-v2 at 3 kbps (68.2 vs 59.9 at 6 kbps). However, its 48 kHz stereophonic implementation faces practical constraints, as its real-time factor (RTF) drops below 1.0 (0.66–0.68) when entropy coding is applied, limiting its utility for real-time streaming.

To address the limitations of standard RVQ, researchers have introduced architectural innovations to improve codebook utilization and compression ratios. The improved RVQGAN (arXiv:2306.06546) achieved 90x compression (44.1 kHz at 8 kbps) by integrating quantizer dropout, which allows a single model to operate across multiple bitrates. This model further mitigates aliasing and codebook collapse through Snake activation functions and factorized/L2-normalized codebooks. While highly efficient, its performance remains domain-dependent, showing lower fidelity for environmental sounds and specific instruments like synthesizers compared to speech.

Recent research has moved toward optimizing the quantization process itself. ERVQ (arXiv:2410.12359) specifically targets speech naturalness by implementing intra- and inter-codebook optimization through online clustering and a code balancing loss to prevent codebook collapse. Complementing these optimizations, SNAC (arXiv:2410.14411) extends the RVQGAN framework into a multi-scale architecture (MS-RVQ). By downsampling residuals before codebook lookup, SNAC operates at different temporal resolutions, providing a versatile framework for music, speech, and environmental sounds.

Finally, the utility of these quantized latent spaces has expanded into the generative domain. SoundStorm (arXiv:2305.09636) leverages the tokens produced by these codecs via a non-autoregressive Transformer-based Conformer architecture. By utilizing bidirectional attention and confidence-based parallel decoding, SoundStorm achieves generation speeds two orders of magnitude faster than autoregressive models, serving as a critical acoustic generator for downstream tasks like AudioLM and MusicLM.

## Streaming, Low-Latency, and Real-Time Communication Codecs

The transition from offline neural audio compression to real-time communication necessitates a fundamental shift toward causal architectures and low-latency processing. Recent research focuses on balancing reconstruction quality with the structural constraints imposed by causality and limited computational budgets.

A primary challenge in streaming is the quality degradation caused by the requirement for causal processing. To address this, arXiv:2504.06561 proposes a fully causal symmetric encoder-decoder structure operating in the MDCT domain. This work introduces a Residual Scalar-Vector Quantizer (RSVQ) specifically designed to improve codebook utilization and compensate for the quality loss inherent in causal structures. While this approach targets high-quality real-time communication and speech language models (SLMs), other researchers have sought to optimize the quantization process itself rather than the structural domain. For instance, arXiv:2509.19186 introduces a beam-search encoding algorithm for Residual Vector Quantization (RVQ) to mitigate quantization error by selecting optimal candidates across iterations. While this improves synthesis quality across speech and music, its applicability to low-latency streaming is less direct than the MDCT-based approach in arXiv:2504.06561.

Methodological approaches to low-bitrate speech coding also diverge between time-frequency domain operations and distillation-based strategies. VoCodec (arXiv:2601.13055) utilizes a Vocos backbone to operate in the time-frequency domain via STFT, leveraging harmonic structures to achieve a latency of 30 ms and a complexity of 349.29M MACs/s. This contrasts with FocalCodec-Stream (arXiv:2509.16195), which employs a causal distillation strategy to adapt WavLM for streaming, combined with focal modulation and a lightweight refiner. While VoCodec focuses on computational efficiency for downstream tasks like noise reduction, FocalCodec-Stream prioritizes extreme bitrate efficiency, achieving 0.55 - 0.80 kbps.

A significant frontier in this domain is the development of perceptually-aware quantization. Moving beyond uniform quantization, arXiv:2606.05892 introduces a voicing-driven quantization mechanism within a fully causal convolutional framework. By utilizing RSVQ for voiced frames and Scalar Quantization (SQ) for unvoiced frames, this method reduces bitrates by approximately 27% compared to baseline models. This represents a more specialized evolution of the residual quantization concepts seen in arXiv:2504.06561, shifting from general codebook utilization to a modulation of bit allocation based on the phonetic characteristics of speech. Collectively, these advancements demonstrate a move toward architectures that are not only causal but also perceptually intelligent, optimizing the trade-off between bitrate, latency, and reconstruction fidelity.

## Bridging Codecs with Language Modeling and Generative Synthesis

Recent research has shifted from treating neural audio codecs as mere compression tools to utilizing their discrete representations as the fundamental building blocks for speech language models (SLMs) and generative synthesis. A foundational shift in this direction is seen in arXiv:2301.02111, which reinterprets zero-shot text-to-speech (TTS) as a conditional language modeling task. By treating discrete codes from the EnCodec framework as tokens, this approach moves away from traditional continuous signal regression, focusing instead on the naturalness and speaker similarity achievable through pure language modeling.

However, the effectiveness of such language modeling is heavily dependent on the quality and structure of the underlying tokens. arXiv:2308.16692 addresses this by introducing SpeechTokenizer, which provides a hierarchical disentanglement of semantic and acoustic information. This method aims to create unified discrete representations that are better suited for SLMs, a claim supported by their SLMTokBench, which assesses token suitability via text alignment and information preservation. While arXiv:2301.02111 relies on existing codec outputs, arXiv:2308.16692 and arXiv:2402.12208 focus on optimizing the tokenization process itself. Specifically, arXiv:2402.12208 proposes a specialized four-codebook channel structure to bridge the gap between discrete codec representations and SLMs, emphasizing robust audio reconstruction across noisy and out-of-domain scenarios.

The methodology for generating speech from these tokens has also diverged into different generative paradigms. One path involves refining the semantic content of the tokens; for instance, arXiv:2407.05407 argues that unsupervised tokens may lack sufficient clarity, proposing instead the use of supervised semantic tokens extracted via a quantizer-augmented ASR model. This approach, combined with auto-regressive LLM generation and conditional flow matching, aims to improve text alignment and naturalness. In contrast, arXiv:2403.03100 pursues a factorized approach. Rather than focusing solely on semantic token supervision, it utilizes factorized diffusion models and codecs to decompose speech into distinct subspaces—content, prosody, timbre, and acoustic details—allowing for individual attribute control during zero-shot synthesis.

Finally, the field is moving toward a more rigorous systematic evaluation of these components. While earlier works focused on specific architectural innovations, arXiv:2409.04016 provides a necessary critical investigation by retraining and comparing high-performing codecs like EnCodec, Vocos, and DAC within a unified SLM framework. This allows for a direct assessment of how different codec systems impact speech generation performance, moving the research frontier from individual model development toward a standardized understanding of how codec-token characteristics dictate the success of downstream speech language modeling.

## Evaluation, Robustness, and Interpretability of Neural Codecs

As neural audio codecs (NACs) transition from foundational compression models to components of generative pipelines, research has shifted toward understanding their reliability, perceptual alignment, and internal representations. Recent literature highlights a multifaceted approach to evaluation, ranging from noise robustness and objective metric correlation to the interpretability of encoded attributes.

A critical dimension of current research is the reliability of objective metrics in approximating human perception. arXiv:2511.19734 conducts a correlation analysis between MUSHRA subjective scores and objective quality metrics across six codecs, specifically targeting speech and speech with background audio. This work is complemented by arXiv:2509.18823, which explores the use of NACs as feature extractors for distance metrics, such as Fréchet Audio Distance (FAD) and Maximum Mean Discrepancy (MMD). While arXiv:2511.19734 focuses on the validity of existing metrics, arXiv:2509.18823 introduces DACe—a high-fidelity version of Descript Audio Codec trained on diverse tonal data—to better correlate embedding distances with subjective MUSHRA/USAC ratings for both speech and music.

Beyond perceptual quality, the robustness of these codecs under non-ideal conditions is a growing concern. arXiv:2505.24248 provides a systematic analysis of how neural speech codecs behave under various noise conditions, extending previous studies to assess their suitability for downstream language modeling and speech processing tasks. This focus on robustness is echoed in the security domain; for instance, arXiv:2603.16914 introduces a quantizer-aware hierarchical aggregation method (QAF-Static) to preserve the Residual Vector Quantization (RVQ) hierarchy, specifically to improve the Equal Error Rate (EER) in speech deepfake detection.

The internal structure of codec tokens also presents opportunities for interpretability and manipulation. arXiv:2506.04492 proposes a two-step framework to probe whether codec tokens contain disentangled information regarding pitch, speaker identity, and linguistic content. By utilizing AnCoGen-Codec plugins, the authors enable the direct prediction and manipulation of these attributes within the token space, moving beyond black-box compression. Similarly, arXiv:2410.22448 investigates the bridge between codec resynthesis and waveform generation. By transitioning from traditional token-based generation to regressing continuous embeddings via a discrete-to-continuous Codec Schrödinger Bridge, this work addresses the fidelity gap in speech generation, offering a more nuanced methodological approach than standard coarse-to-fine regression. Together, these advancements suggest that the frontier of NAC research lies in transforming codecs from simple compression tools into interpretable, robust, and perceptually-aligned representations for complex downstream tasks.

## The Frontier: High-Fidelity, Universal, and Sparse Quantization

Current research in neural audio coding is shifting from general-purpose compression toward specialized architectures that balance high-fidelity reconstruction, semantic disentanglement, and extreme efficiency for edge deployment. A primary trend involves the transition from fixed Residual Vector Quantization (RVQ) to more dynamic, content-adaptive, or sparse quantization strategies. For instance, Switchcodec introduces Residual Experts Vector Quantization (REVQ), which utilizes a hierarchical convolutional backbone to decouple bitrate from codebook capacity through a top-k expert selection strategy (arXiv:2601.20362). This approach achieves near-transparent subjective quality, with MUSHRA scores reaching 93.4 at 5.33 kbps, significantly outperforming established baselines like DAC and EnCodec (arXiv:2601.20362). However, while the novelty of REVQ's sparse activation is clear, the paper's claim of "negligible" routing overhead relies on a specific 2-second windowing assumption and lacks a rigorous analysis of the computational latency introduced by the gating network relative to standard RVQ (arXiv:2601.20362).

Parallel to these quantization advances is the push for "universal" codecs that can handle diverse modalities, such as speech, music, and general acoustics. OmniCodec addresses this by employing a dual-branch architecture that achieves semantic-acoustic disentanglement via an Adapter, allowing for low frame rates of 6.25 Hz or 12.5 Hz (arXiv:2603.20638). This disentanglement is echoed in HybridCodec, which utilizes semantic distillation from SSL representations into a dual-stream architecture to separate semantic and acoustic information without requiring a separate SSL model during inference (arXiv:2606.06743). While OmniCodec focuses on reconstruction and semantic informativeness for downstream LLM generation (arXiv:2603.20638), HybridCodec specifically targets speech discretization for Multimodal Large Language Models (MLLMs) (arXiv:2606.06743).

Specialization for specific bitrates and modalities also defines the frontier. For ultra-low-bitrate speech communication, the P2PSVQ method achieves 0.5 kbps by using a synergistic approach where "pseudo" VQs provide zero-bitrate auxiliary tokens via neural prediction (arXiv:2606.05876). In contrast, TQCodec targets high-fidelity music streaming by employing frequency-aware bit allocation to prioritize lower frequencies within a 32–128 kbps range (arXiv:2603.01592). Finally, for on-device deployment, T-Mimi represents a shift toward architectural simplification; it replaces compute-intensive de-convolution layers with a Transformer-only design using fixed-window streaming self-attention and linear upsampling to reduce latency on mobile CPUs for real-time TTS (arXiv:2601.20094). Together, these developments illustrate a move toward codecs that are not merely efficient bitstream compressors, but intelligent, modality-aware frameworks optimized for specific hardware and downstream generative tasks.

## Tensions and Open Problems

A central debate in the evolution of neural audio modeling concerns the architectural trade-offs between high-fidelity reconstruction and computational efficiency. Early approaches to generative audio often relied on autoregressive modeling of raw waveforms, as seen in the foundational work of arXiv:1609.03499, which prioritized sample-level accuracy but faced significant scalability hurdles. This was challenged by the move toward spectral-domain synthesis in arXiv:1902.08710, which argued that modeling frequency components via adversarial training offers a more efficient path to high-fidelity audio than raw waveform generation. More recently, this tension has shifted toward the design of neural codecs; while arXiv:2309.07405 proposes a highly reproducible and integrable framework for open-source audio modeling, newer research such as arXiv:2601.02776 suggests that such frameworks can be improved through unified, low-bitrate single codebook architectures that utilize sub-band reconstruction to achieve superior efficiency.

Another significant tension exists regarding the methodology of speech synthesis and the role of disentanglement. Traditional end-to-end synthesis models, such as the Tacotron architecture in arXiv:1703.10135, focused on direct mapping from text to spectrograms, but these were often critiqued for a lack of explicit control over acoustic parameters. In response, arXiv:2001.04643 introduced Differentiable Digital Signal Processing (DDSP) to bridge the gap between neural flexibility and classical DSP control. This debate extends into the realm of large-scale language modeling; while arXiv:2209.03143 demonstrated the power of modeling audio as a sequence of discrete tokens, more recent work in arXiv:2403.03100 argues that factorized modeling—as seen in NaturalSpeech 3—provides a more robust zero-shot capability by better separating semantic and acoustic features than the purely token-based approaches found in arXiv:2305.09636.

Finally, there is an ongoing disagreement regarding the optimal granularity of audio tokenization for large-scale modeling. The pursuit of a "universal" tokenizer has led to a divide between multi-scale approaches and unified semantic-acoustic models. For instance, arXiv:2410.14411 argues that multi-scale neural codecs like SNAC provide necessary structural depth that single-scale models lack, specifically critiquing the limitations of unified tokenizers like the one proposed in arXiv:2308.16692. Conversely, the field is moving toward even more complex disentanglement strategies, where models like arXiv:2603.20638 attempt to resolve this by explicitly separating semantic and acoustic information within a low frame-rate universal codec, suggesting that the future of the field lies not in choosing one scale, but in mastering the interplay between them.

## Outlook

The frontier of audio intelligence is rapidly moving away from monolithic, high-bitrate models toward highly specialized, adaptive, and edge-ready architectures. As evidenced by the emergence of sparse quantization techniques in arXiv:2601.20362 and ultra-low latency streaming architectures in arXiv:2604.12438, the next generation of research will likely focus on the convergence of semantic understanding and extreme compression. We anticipate a shift toward "omni-modal" codecs that can simultaneously handle high-fidelity music streaming and low-bitrate speech communication, all while operating within the strict energy constraints of neuromorphic and edge-based hardware.

---

## Key Figures

**High Fidelity Neural Audio Compression** — arXiv:2210.13438 p.2

![2210.13438](figures/2210.13438_p2.png)

The figure illustrates the ENCODEC architecture, consisting of an Encoder, a Quantizer, and a Decoder, with various loss functions ($\ell_w, \ell_d, \ell_g, \ell_s, \ell_t$) indicated by arrows. The diagram shows the flow of audio data through convolutional blocks and vector quantization, which then feeds into a Decoder and a Discriminator composed of STFT and Conv2D blocks. It conveys how the system uses reconstruction and adversarial losses to train the encoder-decoder codec.

**High-Fidelity Audio Compression with Improved RVQGAN** — arXiv:2306.06546 p.4

![2306.06546](figures/2306.06546_p4.png)

This line graph plots entropy in bits on the y-axis against the codebook index on the x-axis. It compares four data series—"Proposed (24kbps)", "Proposed", "EnCodec", and "Proposed (w/ EMA)"—showing how entropy values change across different codebook indices for each method.

**Neural Codec Language Models are Zero-Shot Text to Speech Synthesizers** — arXiv:2301.02111 p.1

![2301.02111](figures/2301.02111_p1.png)

The figure illustrates the VALL-E architecture, showing a pipeline that transforms a text prompt and a 3-second acoustic prompt into personalized speech. It depicts a process where text is converted to phonemes and an acoustic prompt is processed by an audio codec encoder, both of which feed into a neural codec language modeling block to generate discrete codes. These codes are then processed by an audio codec decoder to produce the final personalized speech waveform.

**HuBERT: Self-Supervised Speech Representation Learning by Masked
  Prediction of Hidden Units** — arXiv:2106.07447 p.2

![2106.07447](figures/2106.07447_p2.png)

The figure depicts a block diagram of the HuBERT architecture, showing a CNN Encoder at the bottom, a Transformer layer in the middle, and an Acoustic Unit Discovery System at the top. Arrows indicate a flow where input frames ($x_1$ through $x_6$) and masked frames ([MSK]) pass through the encoder and transformer to predict hidden unit assignments ($z_1$ through $z_6$). The diagram conveys that the model learns by predicting the cluster assignments of masked frames based on the acoustic units discovered by the top system.

**SoundStream: An End-to-End Neural Audio Codec** — arXiv:2107.03312 p.1

![2107.03312](figures/2107.03312_p1.png)

This scatter plot compares different audio codecs by plotting MUSHRA scores on the y-axis against bitrate in kbps on the x-axis. The figure displays data points for SoundStream, SoundStream-scalable, EVS, Opus, and Lyra, using various colored markers and error bars to convey the perceptual quality of each codec at specific bitrates.

**Neural Discrete Representation Learning** — arXiv:1711.00937 p.4

![1711.00937](figures/1711.00937_p4.png)

The left panel illustrates the VQ-VAE architecture, showing an input image passing through a CNN encoder to produce $z(x)$, which is then mapped to a discrete embedding $q(z)$ from an embedding space before being processed by a CNN decoder to reconstruct the image. The right panel visualizes the embedding space as a collection of points, where a red arrow represents the gradient $\nabla_z L$ pushing the encoder output $z(x)$ toward the nearest discrete embedding $e_2$.

**AudioLM: a Language Modeling Approach to Audio Generation** — arXiv:2209.03143 p.3

![2209.03143](figures/2209.03143_p3.png)

The figure illustrates the two tokenization processes used in AudioLM, showing an audio waveform being processed by two separate pathways. The first pathway uses SoundStream (comprising an Encoder, Residual Vector Quantizer, and Decoder) to produce acoustic tokens, while the second pathway passes the audio through a w2v-BERT model to an intermediate layer, which is then processed by k-means to produce semantic tokens.

**Attention Is All You Need** — arXiv:1706.03762 p.3

![1706.03762](figures/1706.03762_p3.png)

The figure illustrates the Transformer model architecture, consisting of an encoder stack on the left and a decoder stack on the right, both composed of $N$ identical layers. The diagram uses colored boxes to represent functional components—such as Multi-Head Attention, Feed Forward, and Add & Norm—connected by arrows to show the flow from input embeddings and positional encodings to the final softmax output probabilities.

**Switchcodec: Adaptive residual-expert sparse quantization for high-fidelity neural audio coding** — arXiv:2601.20362 p.2

![2601.20362](figures/2601.20362_p2.png)

The figure illustrates the SwitchCodec architecture, showing a sequential flow from an input audio waveform through an Encoder, a dual-path quantization module, an Add operation, a Decoder, and finally a Discriminator. The quantization module, enclosed in a red dashed box, consists of a Shared Quantizer and a Router that directs information to a set of experts ($Q_1, Q_2, \dots, Q_n$). This design conveys a process where a base code and a refined residual are summed to produce the quantized representation.

**TQCodec: Towards neural audio codec for high-fidelity music streaming** — arXiv:2603.01592 p.3

![2603.01592](figures/2603.01592_p3.png)

The figure illustrates a perception-driven subband modeling process consisting of three stages: PQMF pre-processing, PQMF analysis (subband=16), and PQMF synthesis (subband=16). It uses boxes to represent modules (Encoder, Decoder, and PQMF components) and arrows to show the flow of signals, such as $x_{subband}$ and $z_{subband}$, through the system. The diagram conveys how an input signal is decomposed into multiple subbands for encoding and subsequently reconstructed through a synthesis stage.

**UniSRCodec: Unified and Low-Bitrate Single Codebook Codec with Sub-Band Reconstruction** — arXiv:2601.02776 p.3

![2601.02776](figures/2601.02776_p3.png)

The figure illustrates the architecture of UniSRCodec, showing a flow from an Encoder to a Decoder through a SimVQ quantization module. The process involves transforming input into a latent representation, which is then frame-wise flattened, quantized via SimVQ, and re-formed into a quantized latent before decoding. The bottom panel displays the training procedure involving spectral discriminators and sub-band reconstruction losses for high-frequency and low-frequency components.

**Quantizer-Aware Hierarchical Neural Codec Modeling for Speech Deepfake Detection** — arXiv:2603.16914 p.2

![2603.16914](figures/2603.16914_p2.png)

The figure presents a flowchart of the proposed speech deepfake detection framework, illustrating the fusion of SSL features from WavLM (via Attentive Merging) with codec representations. It depicts the integration process through quantizer-aware weighting across RVQ levels and includes a quantizer mean pooling baseline for comparison.

**An Ultra-Low-Bitrate Neural Speech Codec with Plain-to-Pseudo Synergistic Vector Quantization** — arXiv:2606.05876 p.1

![2606.05876](figures/2606.05876_p1.png)

The figure presents a block diagram of the P2SynCodec architecture, consisting of an encoder, a P2PSVQ module, and a decoder connected by arrows. The P2PSVQ module is depicted as a cascaded structure where a "plain VQ" produces basic tokens that are then passed to multiple "pseudo VQs" to predict auxiliary tokens. The diagram conveys the end-to-end process of downsampling speech, quantizing representations through plain-to-pseudo synergistic vector quantization, and reconstructing the waveform.
