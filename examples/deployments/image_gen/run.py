"""Client script: chain image-gen nodes like a ComfyUI workflow.

Usage:
    python3 examples/deployments/image_gen/run.py
"""

import asyncio
from pathlib import Path
from deploy import txt2img, img2img, upscale


async def main():
    prompt = "a corgi astronaut floating in space, earth in background, cinematic lighting"
    negative = "blurry, low quality, watermark, text"

    # --- Node 1: txt2img ---
    print("Generating 1024x1024 base image ...")
    base_png = await txt2img(prompt, negative_prompt=negative, steps=30, seed=42)
    Path("01_base.png").write_bytes(base_png)
    print(f"  -> 01_base.png ({len(base_png)} bytes)")

    # --- Node 2: img2img style transfer ---
    print("Applying style with img2img ...")
    styled_png = await img2img(
        base_png,
        prompt=f"{prompt}, watercolor",
        negative_prompt=negative,
        strength=0.8,
        steps=25,
    )
    Path("02_styled.png").write_bytes(styled_png)
    print(f"  -> 02_styled.png ({len(styled_png)} bytes)")

    # --- Node 3: 4x upscale (1024x1024 -> 4096x4096) ---
    print("Upscaling 4x ...")
    upscaled_png = await upscale(styled_png, prompt=prompt)
    Path("03_upscaled.png").write_bytes(upscaled_png)
    print(f"  -> 03_upscaled.png ({len(upscaled_png)} bytes)")

    print("Done! Pipeline: txt2img -> img2img -> upscale 4x")


if __name__ == "__main__":
    asyncio.run(main())
