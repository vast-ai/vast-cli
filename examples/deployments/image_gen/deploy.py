"""Minimal ComfyUI-style image generation deployment.

Exposes a node-based workflow as composable remote functions:
  - txt2img: text prompt -> image bytes
  - img2img: image bytes + prompt -> image bytes
  - upscale: image bytes -> upscaled image bytes

Each function returns PNG bytes directly, so callers can chain them
client-side just like wiring nodes in ComfyUI:

    base = await txt2img("a cat in space", steps=30)
    refined = await img2img(base, "a cat in space, highly detailed", strength=0.4)
    final = await upscale(refined, scale_factor=2)
    Path("output.png").write_bytes(final)
"""

import random
from vastai import Deployment
from vastai.data.query import gpu_name, RTX_4090, RTX_5090

app = Deployment(name="image-gen", tag="v2")

MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"
REFINER_ID = "stabilityai/stable-diffusion-xl-refiner-1.0"

# ---------------------------------------------------------------------------
# Context: load models once per worker, keep them warm on GPU
# ---------------------------------------------------------------------------

@app.context()
class DiffusionModels:
    async def __aenter__(self):
        import torch, sys, logging
        from diffusers import StableDiffusionXLPipeline, StableDiffusionXLImg2ImgPipeline, StableDiffusionUpscalePipeline
        from diffusers.utils import logging as diffusers_logging

        # Enable verbose download & loading logs
        diffusers_logging.set_verbosity_info()
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] %(name)s %(levelname)s: %(message)s",
            stream=sys.stdout,
        )
        # huggingface_hub download progress
        try:
            import huggingface_hub
            huggingface_hub.utils.logging.set_verbosity_info()
        except Exception:
            pass

        dtype = torch.float16
        device = "cuda"

        print(f"[image-gen] Downloading & loading base model: {MODEL_ID}", flush=True)
        self.txt2img_pipe = StableDiffusionXLPipeline.from_pretrained(
            MODEL_ID, torch_dtype=dtype, variant="fp16", use_safetensors=True,
        )
        print(f"[image-gen] Moving base model to {device} ...", flush=True)
        self.txt2img_pipe = self.txt2img_pipe.to(device)
        print(f"[image-gen] Base model loaded on {device}.", flush=True)

        # Reuse base model components for img2img to save VRAM
        print("[image-gen] Creating img2img pipeline (shared weights) ...", flush=True)
        self.img2img_pipe = StableDiffusionXLImg2ImgPipeline(
            vae=self.txt2img_pipe.vae,
            text_encoder=self.txt2img_pipe.text_encoder,
            text_encoder_2=self.txt2img_pipe.text_encoder_2,
            tokenizer=self.txt2img_pipe.tokenizer,
            tokenizer_2=self.txt2img_pipe.tokenizer_2,
            unet=self.txt2img_pipe.unet,
            scheduler=self.txt2img_pipe.scheduler,
        )

        # Warmup: single-step generation to trigger CUDA graph compilation
        print("[image-gen] Warming up (1-step latent generation) ...", flush=True)
        self.txt2img_pipe(
            "warmup", num_inference_steps=1, output_type="latent",
        )

        # SD x4 upscaler (separate model, shares nothing with SDXL)
        UPSCALER_ID = "stabilityai/stable-diffusion-x4-upscaler"
        print(f"[image-gen] Downloading & loading upscaler: {UPSCALER_ID}", flush=True)
        self.upscale_pipe = StableDiffusionUpscalePipeline.from_pretrained(
            UPSCALER_ID, torch_dtype=dtype,
        ).to(device)
        self.upscale_pipe.set_progress_bar_config(disable=True)
        self.upscale_pipe.enable_vae_tiling()
        self.upscale_pipe.enable_attention_slicing()
        print(f"[image-gen] Upscaler loaded on {device}.", flush=True)

        self.device = device
        self.dtype = dtype
        print("[image-gen] All models ready. Accepting requests.", flush=True)
        return self

    async def __aexit__(self, *exc):
        pass


# ---------------------------------------------------------------------------
# Remote functions (the "nodes")
# ---------------------------------------------------------------------------

BENCHMARK_PROMPTS = [
    {"prompt": "a photograph of an astronaut riding a horse"},
    {"prompt": "oil painting of a sunset over mountains"},
    {"prompt": "cyberpunk cityscape at night, neon lights"},
]


@app.remote(benchmark_dataset=BENCHMARK_PROMPTS)
async def txt2img(
    prompt: str,
    negative_prompt: str = "",
    width: int = 1024,
    height: int = 1024,
    steps: int = 30,
    guidance_scale: float = 7.5,
    seed: int = -1,
) -> bytes:
    """Generate an image from a text prompt. Returns PNG bytes."""
    import torch, io
    from PIL import Image

    ctx = app.get_context(DiffusionModels)

    generator = torch.Generator(device=ctx.device)
    if seed >= 0:
        generator.manual_seed(seed)
    else:
        generator.manual_seed(random.randint(0, 2**32 - 1))

    result = ctx.txt2img_pipe(
        prompt=prompt,
        negative_prompt=negative_prompt or None,
        width=width,
        height=height,
        num_inference_steps=steps,
        guidance_scale=guidance_scale,
        generator=generator,
    )

    buf = io.BytesIO()
    result.images[0].save(buf, format="PNG")
    return buf.getvalue()


@app.remote()
async def img2img(
    image_bytes: bytes,
    prompt: str,
    negative_prompt: str = "",
    strength: float = 0.5,
    steps: int = 30,
    guidance_scale: float = 7.5,
    seed: int = -1,
) -> bytes:
    """Refine an existing image with a text prompt. Returns PNG bytes."""
    import torch, io
    from PIL import Image

    ctx = app.get_context(DiffusionModels)

    input_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    generator = torch.Generator(device=ctx.device)
    if seed >= 0:
        generator.manual_seed(seed)
    else:
        generator.manual_seed(random.randint(0, 2**32 - 1))

    result = ctx.img2img_pipe(
        prompt=prompt,
        negative_prompt=negative_prompt or None,
        image=input_image,
        strength=strength,
        num_inference_steps=steps,
        guidance_scale=guidance_scale,
        generator=generator,
    )

    buf = io.BytesIO()
    result.images[0].save(buf, format="PNG")
    return buf.getvalue()


@app.remote()
async def upscale(
    image_bytes: bytes,
    prompt: str = "",
    steps: int = 20,
    seed: int = -1,
) -> bytes:
    """4x upscale using Stable Diffusion x4 upscaler. Returns PNG bytes."""
    import torch, io
    from PIL import Image

    ctx = app.get_context(DiffusionModels)

    low_res = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    generator = torch.Generator(device=ctx.device)
    if seed >= 0:
        generator.manual_seed(seed)
    else:
        generator.manual_seed(random.randint(0, 2**32 - 1))

    result = ctx.upscale_pipe(
        prompt=prompt or "",
        image=low_res,
        num_inference_steps=steps,
        generator=generator,
    )

    buf = io.BytesIO()
    result.images[0].save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Image & deployment config
# ---------------------------------------------------------------------------

image = app.image("vastai/pytorch:@vastai-automatic-tag", 50)
image.venv("/venv/main")
image.pip_install(
    "diffusers>=0.30.0",
    "transformers>=4.40.0",
    "accelerate",
    "safetensors",
    "invisible-watermark>=0.2.0",
)
image.require(gpu_name.in_([RTX_4090, RTX_5090]))
app.configure_autoscaling(min_load=10, max_workers=5) #!VAST_IGNORE_CHANGES
app.ensure_ready()
