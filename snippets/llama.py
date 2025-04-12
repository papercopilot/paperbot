import transformers
import torch

model_id = "meta-llama/Meta-Llama-3-8B-Instruct"

pipeline = transformers.pipeline(
  "text-generation",
#   model="meta-llama/Meta-Llama-3-8B-Instruct",
  model="meta-llama/Meta-Llama-3.1-8B-Instruct",
  model_kwargs={"torch_dtype": torch.bfloat16},
  device="cuda",
)


text = "Unmixing Diffusion for Self-Supervised Hyperspectral Image Denoising \
Haijin Zeng 1 \
Jiezhang Cao 2* Kai Zhang 3 Yongyong Chen 4 Hiep Luong 1 Wilfried Philips 1 \
1 \
IMEC-UGent 2 ETH Zurich 3 Nanjing University 4 Harbin Institute of Technology, Shenzhen \
{Haijin.Zeng, Hiep.Luong, Wilfried.Philips}@UGent.be, jiezhang.cao@vision.ee.ethz.ch \
Abstract \
Hyperspectral images (HSIs) have extensive applications in various fields such as medicine, agriculture, and \
industry. Nevertheless, acquiring high signal-to-noise ratio HSI poses a challenge due to narrow-band spectral filtering. Consequently, the importance of HSI denoising is \
substantial, especially for snapshot hyperspectral imaging \
technology. While most previous HSI denoising methods \
are supervised, creating supervised training datasets for \
the diverse scenes, hyperspectral cameras, and scan parameters is impractical. In this work, we present DiffUnmix, a self-supervised denoising method for HSI using diffusion denoising generative models. Specifically, \
Diff-Unmix addresses the challenge of recovering noisedegraded HSI through a fusion of Spectral Unmixing and \
conditional abundance generation. Firstly, it employs a \
learnable block-based spectral unmixing strategy, complemented by a pure transformer-based backbone. Then, we \
introduce a self-supervised generative diffusion network to \
enhance abundance maps from the spectral unmixing block. \
This network reconstructs noise-free Unmixing probability \
distributions, effectively mitigating noise-induced degradations within these components. Finally, the reconstructed \
HSI is reconstructed through unmixing reconstruction by \
blending the diffusion-adjusted abundance map with the \
spectral endmembers. Experimental results on both simulated and real-world noisy datasets show that Diff-Unmix \
achieves state-of-the-art performance. \
1. Introduction \
Hyperspectral images (HSIs) offer richer spectral information compared to RGB images, making them valuable for \
various applications such as face recognition [48, 49], vegetation detection [6], and medical diagnosis [54]. However, \
the substantial number of spectral bands in HSIs, combined \
with scanning designs [3] and narrow band spectral filtering, results in limited photon counts per band, making HSIs \
susceptible to noise [62]. This noise not only degrades \
*Corresponding Author \
Hyperspectral Image Toy \
GT Patch Noisy Patch \
DDS2M Diff-Unmix \
Figure 1. Comparison (wavelength 600nm) between diffusion \
based DDS2M [36] and the proposed Diff-Unmix on a hyperspectral image Toy corrupted with Gaussian noise N (0, 0.3). DiffUnmix shows the ability to restore fine details by leveraging a pretrained diffusion model on RGB images. \
visual quality but also hinders downstream tasks, which \
makes denoising a crucial pre-processing step. \
Similar to RGB images, HSIs exhibit spatial selfsimilarity, implying that similar pixels can be jointly denoised. Furthermore, HSIs possess inherent spectral correlations due to their nominal spectral resolution. Consequently, effective denoising methods for HSIs must consider the prior within both spatial and spectral domains. \
Traditional model-based HSI denoising approaches [11, 17, \
22] rely on handcrafted priors to capture spatial and spectral correlations through iterative optimization. These methods often employ priors like total variation [20, 22, 68], \
non-local similarity [18], low-rank [9, 10] properties, and \
sparsity [53]. Nonetheless, the effectiveness of these methods relies heavily on the precision of manually crafted priors. Furthermore, model-based denoising entails significant \
computational demands due to iterative processes and may \
struggle to generalize across a wide range of scenarios. \
To achieve robust noise removal, deep learning approaches [7, 44, 52, 60] have been applied to HSI denoising, achieving impressive results. However, many of these \
methods employ convolutional neural networks (CNNs) for \
feature extraction, relying on local filter responses within \
a limited receptive field to distinguish noise from signal. \
Recently, vision Transformers have shown promise in various tasks, including both high-level [16, 50] and low"

# prompt = f"""[INST] Extract authors' names, emails, affiliations, and links from the following text:\n{text}\n[/INST]"""
prompt = """
    [INST] 
    Extract and summarize the following content into the specified JSON format.
    Follow these rules strictly:
    1. Identify the paper's title.
    2. Extract all authors in order, separated by semicolons.
    3. Extract the corresponding affiliations for each author in the same order, separated by semicolons. If the text uses numbering or symbols (e.g., ¹, *, †) to map authors to affiliations, preserve that matching.
    4. Extract the corresponding emails for each author in the same order, separated by semicolons. If an email is not provided for an author, use an empty string "" as a placeholder.
    5. Extract a project link (non-GitHub) if available, otherwise use an empty string "".
    6. Extract a GitHub link if available, otherwise use an empty string "".
    
    Special Rule for Emails:
    - If emails are written like `{alice, bob}@usc.edu`, expand them to `alice@usc.edu; bob@usc.edu` accordingly.
    
    Important:
    - Output ONLY a valid JSON object in the exact structure shown below.
    - Do NOT include any extra explanation, text, or comment.
    - Always return every key, even if the value is empty.
    
    Output JSON format::
    ```json 
        { 
            "title": "{{title of the paper}}", 
            "authors": "{{name of the first author}}; {{name of the second author}}; ...",
            "aff": "{{affiliation of the first author}}; {{affiliation of the second author}}; ...",
            "email": "{{email of the first author}}; {{email of the second author}}; ...",
            "github": "{{github link if available, otherwise empty}}", 
            "project": "{{project link if available and not github, otherwise empty}}", 
        }
    ```
   Text to parse:\n
    """ + text + """ [/INST]"""

output = pipeline(prompt, max_new_tokens=300)
generated_only = output[0]["generated_text"].split('[/INST]')[-1].strip()
print(generated_only)

# meta-llama/Meta-Llama-3-8B-Instruct
# 1. Haijin Zeng
#         * Email: [Haijin.Zeng@UGent.be](mailto:Haijin.Zeng@UGent.be)
#         * Affiliation: IMEC-UGent
# 2. Jiezhang Cao
#         * Email: [jiezhang.cao@vision.ee.ethz.ch](mailto:jiezhang.cao@vision.ee.ethz.ch)
#         * Affiliation: ETH Zurich
# 3. Kai Zhang
#         * No email or affiliation mentioned
# 4. Yongyong Chen
#         * No email or affiliation mentioned
# 5. Hiep Luong
#         * Email: [Hiep.Luong@UGent.be](mailto:Hiep.Luong@UGent.be)
#         * Affiliation: IMEC-UGent
# 6. Wilfried Philips
#         * Email: [Wilfried.Philips@UGent.be](mailto:Wilfried.Philips@UGent.be)
#         * Affiliation: IMEC-UGent