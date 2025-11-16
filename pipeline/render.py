from dataclasses import dataclass
from typing import Dict, Tuple

from PIL import Image, ImageDraw, ImageFont

from .core import CampaignBrief


AspectRatio = Tuple[int, int]

ASPECT_RATIOS: Dict[str, AspectRatio] = {
    "1:1": (1, 1),
    "9:16": (9, 16),
    "16:9": (16, 9),
}


@dataclass
class BrandSettings:
    primary_color: tuple[int, int, int]


def resize_to_aspect_ratio(img: Image.Image, ratio: AspectRatio) -> Image.Image:
    """
    Resize + crop to the requested aspect ratio while filling the frame.
    """
    target_w, target_h = ratio
    base_size = 1200
    if target_w >= target_h:
        width = base_size
        height = int(base_size * (target_h / target_w))
    else:
        height = base_size
        width = int(base_size * (target_w / target_h))

    img = img.copy()
    img.thumbnail((width, height), Image.LANCZOS)

    # Create a canvas and paste in the center
    canvas = Image.new("RGB", (width, height), color=(0, 0, 0))
    x = (width - img.width) // 2
    y = (height - img.height) // 2
    canvas.paste(img, (x, y))
    return canvas


def overlay_campaign_text(
    img: Image.Image,
    campaign: CampaignBrief,
    product: dict,
) -> Image.Image:
    """
    Render English messaging onto the image, using brand color and
    a simple readability check (text + gradient overlay).
    """
    img = img.convert("RGBA")
    w, h = img.size

    brand_color = _parse_color(campaign.primary_color)
    headline = campaign.messaging.headline
    subheading = campaign.messaging.subheading
    cta = campaign.messaging.call_to_action
    product_name = product.get("name")

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Gradient at the bottom for readability
    gradient_height = int(h * 0.45)
    for i in range(gradient_height):
        alpha = int(220 * (i / gradient_height))
        draw.line(
            [(0, h - gradient_height + i), (w, h - gradient_height + i)],
            fill=(0, 0, 0, alpha),
        )

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Fonts
    headline_font = _load_font(campaign.font_path, size=int(h * 0.06))
    body_font = _load_font(campaign.font_path, size=int(h * 0.035))
    cta_font = _load_font(campaign.font_path, size=int(h * 0.04))

    margin_x = int(w * 0.07)
    y = int(h * 0.6)

    # Product name (small label)
    if product_name:
        y = _draw_text_block(
            draw,
            text=str(product_name),
            font=body_font,
            max_width=w - 2 * margin_x,
            x=margin_x,
            y=y,
            fill=(209, 213, 219),  # gray-300
            line_spacing=6,
        ) + 8

    # Headline in brand color
    y = _draw_text_block(
        draw,
        text=headline,
        font=headline_font,
        max_width=w - 2 * margin_x,
        x=margin_x,
        y=y,
        fill=brand_color,
        line_spacing=8,
    ) + 6

    if subheading:
        y = _draw_text_block(
            draw,
            text=subheading,
            font=body_font,
            max_width=w - 2 * margin_x,
            x=margin_x,
            y=y,
            fill=(229, 231, 235),  # gray-200
            line_spacing=6,
        ) + 12

    if cta:
        # CTA pill
        text_w = draw.textlength(cta, font=cta_font)
        padding_x = 18
        padding_y = 8
        box_w = int(text_w + 2 * padding_x)
        box_h = int(cta_font.getbbox(cta)[3] + 2 * padding_y)

        box_x0 = margin_x
        box_y0 = y
        box_x1 = box_x0 + box_w
        box_y1 = box_y0 + box_h

        draw.rounded_rectangle(
            [box_x0, box_y0, box_x1, box_y1],
            radius=box_h // 2,
            fill=brand_color,
        )
        draw.text(
            (box_x0 + padding_x, box_y0 + padding_y),
            cta,
            font=cta_font,
            fill=(255, 255, 255),
        )

    return img.convert("RGB")


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    x: int,
    y: int,
    fill: tuple[int, int, int],
    line_spacing: int,
) -> int:
    lines = _wrap_text(draw, text, font, max_width)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.getbbox(line)[3] + line_spacing
    return y


def _wrap_text(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=font) <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _parse_color(color_str: str) -> tuple[int, int, int]:
    """
    Parse hex color strings like '#FF0000' or 'FF0000' into RGB tuple.
    Fallbacks to a safe default if parsing fails.
    """
    s = color_str.strip().lstrip("#")
    try:
        if len(s) == 6:
            r = int(s[0:2], 16)
            g = int(s[2:4], 16)
            b = int(s[4:6], 16)
            return (r, g, b)
    except Exception:
        pass
    return (59, 130, 246)  # blue-500


def _load_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_path:
        try:
            return ImageFont.truetype(font_path, size=size)
        except Exception:
            pass
    try:
        return ImageFont.truetype("arial.ttf", size=size)
    except Exception:
        return ImageFont.load_default()


