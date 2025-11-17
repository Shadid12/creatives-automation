import base64
import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from PIL import Image


DEFAULT_SIZE = (1024, 1024)


@dataclass
class ImageGenerator:

    use_mock: bool = True  # Kept for backwards-compatibility; no longer used.

    def generate_image(self, prompt: str, size: Tuple[int, int] = DEFAULT_SIZE) -> Image.Image:
        return self._real_generate(prompt, size=size)

    @staticmethod
    def load_existing_image(path: Path) -> Image.Image:
        return Image.open(path).convert("RGB")

    def _real_generate(self, prompt: str, size: Tuple[int, int]) -> Image.Image:
        """
        Call the Replicate API to generate an ad-style product image using Imagen 4 Fast.

        Requires REPLICATE_API_TOKEN to be set in the environment and the `replicate`
        package to be installed.
        """
        import replicate

        api_token = os.environ.get("REPLICATE_API_TOKEN")
        if not api_token:
            raise RuntimeError(
                "REPLICATE_API_TOKEN is not set. A valid API token is required for image generation."
            )

        width, height = size
        # Always generate 1:1 for maximum flexibility and quality
        aspect_ratio = "1:1"

        print(f"Image Generator Prompt: {prompt}")
        
        # Enhance prompt to prevent text generation
        enhanced_prompt = f"{prompt}. IMPORTANT: Do not include any text, letters, words, or typography in the image. Pure product photography only, no text elements."

        input_params = {
            "prompt": enhanced_prompt,
            "aspect_ratio": aspect_ratio,
            "megapixels": "1"  # Generate largest size (1 megapixel = maximum resolution)
        }

        output = replicate.run(
            "google/imagen-4-fast",
            input=input_params
        )

        # Download the image from the URL
        image_bytes = output.read()
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # If the requested size is different from the generated size,
        # resize while preserving aspect ratio.
        if img.size != size:
            img = img.resize(size, Image.LANCZOS)

        return img
