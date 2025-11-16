from dataclasses import dataclass
from pathlib import Path
from typing import List

from PIL import Image, ImageDraw, ImageFont


DEFAULT_SIZE = (1024, 1024)


@dataclass
class ImageGenerator:
    """
    Adapter for GenAI image generation.

    In this local version we only implement a deterministic mock that:
    - creates a solid background
    - overlays the prompt text in a small caption
    This keeps the pipeline fully local and testable.
    """

    use_mock: bool = True

    def generate_image(self, prompt: str, size=DEFAULT_SIZE) -> Image.Image:
        if self.use_mock:
            return self._mock_generate(prompt, size=size)
        # Placeholder for a real GenAI integration (e.g. API call)
        # In this template we keep it unimplemented on purpose.
        raise NotImplementedError("Real GenAI generator is not implemented in this local template.")

    @staticmethod
    def load_existing_image(path: Path) -> Image.Image:
        return Image.open(path).convert("RGB")

    def _mock_generate(self, prompt: str, size=DEFAULT_SIZE) -> Image.Image:
        """
        Create a simple but readable mock asset so you can visually
        inspect that the pipeline is working.
        """
        img = Image.new("RGB", size, color=(17, 24, 39))  # tailwind gray-900-ish
        draw = ImageDraw.Draw(img)

        font = _load_default_font(18)
        # Take a short prefix of the prompt to keep it legible
        snippet = (prompt[:140] + "...") if len(prompt) > 140 else prompt

        margin = 32
        text_box_width = size[0] - 2 * margin
        wrapped = _wrap_text(draw, snippet, font, text_box_width)

        # Draw a semi-transparent rectangle behind the text
        text_height = sum(font.getbbox(line)[3] for line in wrapped) + 8 * len(wrapped)
        box_top = size[1] - text_height - 2 * margin
        box_bottom = size[1] - margin

        overlay = Image.new("RGBA", (size[0], size[1]), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle(
            [margin // 2, box_top, size[0] - margin // 2, box_bottom],
            fill=(0, 0, 0, 180),
        )
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        y = box_top + 16
        for line in wrapped:
            draw.text((margin, y), line, font=font, fill=(255, 255, 255))
            y += font.getbbox(line)[3] + 8

        return img


def _load_default_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size=size)
    except Exception:
        return ImageFont.load_default()


def _wrap_text(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int
) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        width = draw.textlength(test, font=font)
        if width <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


