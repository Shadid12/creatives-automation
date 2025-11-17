import base64
import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from PIL import Image


DEFAULT_SIZE = (1024, 1024)


@dataclass
class ImageGenerator:

    use_mock: bool = True  # Kept for backwards-compatibility; no longer used.

    def generate_image(
        self,
        prompt: str,
        size: Tuple[int, int] = DEFAULT_SIZE,
        product_info: Optional[Dict] = None,
        demographics: Optional[Dict] = None,
        locale: Optional[str] = None,
        brand_name: Optional[str] = None,
    ) -> Image.Image:
        """
        Generate an image using AI. If product_info is provided, uses OpenAI to
        create an enhanced prompt before generating the image.
        """
        # If we have product context, use OpenAI to create a better prompt
        if product_info:
            enhanced_prompt = self._generate_prompt_with_openai(
                base_prompt=prompt,
                product_info=product_info,
                demographics=demographics,
                locale=locale,
                brand_name=brand_name,
            )
        else:
            enhanced_prompt = prompt
            
        return self._real_generate(enhanced_prompt, size=size)

    @staticmethod
    def load_existing_image(path: Path) -> Image.Image:
        return Image.open(path).convert("RGB")

    def _generate_prompt_with_openai(
        self,
        base_prompt: str,
        product_info: Dict,
        demographics: Optional[Dict] = None,
        locale: Optional[str] = None,
        brand_name: Optional[str] = None,
    ) -> str:
        """
        Use OpenAI to generate an optimized image generation prompt based on
        product information, demographics, and locale.
        """
        from openai import OpenAI
        
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("⚠️  OPENAI_API_KEY not set. Using base prompt without enhancement.")
            return base_prompt
        
        client = OpenAI(api_key=api_key)
        
        # Build context for OpenAI
        product_name = product_info.get("name", "product")
        product_description = product_info.get("description", "")
        product_tags = product_info.get("tags", [])
        
        demographics_str = ""
        if demographics:
            demo_parts = [f"{k}: {v}" for k, v in demographics.items()]
            demographics_str = ", ".join(demo_parts)
        
        locale_str = locale or "en-US"
        brand_str = brand_name or "a brand"
        tags_str = ", ".join(product_tags) if product_tags else "general product"
        
        system_message = """You are an expert at creating image generation prompts for advertising and marketing photography. 
Your task is to create a detailed, effective prompt for an AI image generator that will produce high-quality product photography suitable for digital marketing campaigns.

Key requirements:
- Focus on visual composition, lighting, and styling
- Consider the target demographic and locale when suggesting styling
- Be specific about photography style and atmosphere
- DO NOT include any text, typography, or words in the image
- Create prompts that result in clean, professional product photography
- Keep prompts concise but descriptive (2-4 sentences max)"""

        user_message = f"""Create an image generation prompt for this product:

Product: {product_name}
Description: {product_description}
Tags: {tags_str}
Brand: {brand_str}
Target Demographics: {demographics_str}
Locale: {locale_str}

Base prompt for reference: {base_prompt}

Generate a refined, detailed prompt for an AI image generator that will create an attractive product photograph for this marketing campaign. Focus on visual elements only - no text or typography should appear in the image."""

        try:
            print(f"🤖 Calling OpenAI to generate enhanced image prompt...")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=300,
            )
            
            enhanced_prompt = response.choices[0].message.content.strip()
            print(f"✨ OpenAI Enhanced Prompt: {enhanced_prompt}")
            return enhanced_prompt
            
        except Exception as e:
            print(f"⚠️  Error calling OpenAI: {e}. Using base prompt.")
            return base_prompt

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

        print(f"🎨 Final Image Generator Prompt: {prompt}")
        
        # Add a final reminder to prevent text generation
        final_prompt = f"{prompt}. IMPORTANT: Do not include any text, letters, words, or typography in the image. Pure product photography only, no text elements."

        input_params = {
            "prompt": final_prompt,
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
