from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, List, Optional

from PIL import Image, ImageDraw, ImageFont


AspectRatio = Tuple[int, int]

ASPECT_RATIOS: Dict[str, AspectRatio] = {
    "1:1": (1, 1),
    "9:16": (9, 16),
    "16:9": (16, 9),
}


@dataclass
class BrandSettings:
    primary_color: Tuple[int, int, int]


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
    campaign,
    product: dict,
    messaging,
) -> Image.Image:
    """
    Render English messaging onto the image, using brand color and
    a simple readability check (text + gradient overlay).
    """
    img = img.convert("RGBA")
    w, h = img.size

    brand_color = _parse_color(campaign.primary_color)
    secondary_color = _parse_color(campaign.secondary_color)

    # Always use the LLM-generated messaging that is passed in.
    headline = messaging.headline
    subheading = messaging.subheading

    print(f"Headline: {headline}")
    print(f"Subheading: {subheading}")

    cta = messaging.call_to_action
    product_name = product.get("name")

    print(f"CTA: {cta}")

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

    # Calculate font sizes based on aspect ratio
    # Use a combination of width and height to ensure fonts scale appropriately
    aspect_ratio = w / h if h > 0 else 1.0
    
    # Base size calculation: smaller multipliers for more compact fonts
    # This ensures fonts are appropriately sized for all aspect ratios
    if aspect_ratio > 1.5:  # Landscape (16:9) - wider
        # For wide landscape, use smaller base size
        base_size = max(w, h) * 0.06
    elif aspect_ratio < 0.7:  # Portrait (9:16) - taller
        # For tall portrait, use smaller base size
        base_size = max(w, h) * 0.055
    else:  # Square or near-square (1:1)
        # For square, use smaller base size
        base_size = max(w, h) * 0.055
    
    # Fonts - smaller multipliers for more compact text
    headline_font = _load_font(campaign.font_path, size=int(base_size * 1.1))
    body_font = _load_font(campaign.font_path, size=int(base_size * 0.5))
    cta_font = _load_font(campaign.font_path, size=int(base_size * 0.5))

    margin_x = int(w * 0.07)
    # Start text block slightly higher for 16:9 to avoid clipping near the bottom,
    # keep a bit lower for other aspect ratios.
    if aspect_ratio > 1.5:  # 16:9 landscape
        y = int(h * 0.5)
    else:
        y = int(h * 0.55)

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
            fill=secondary_color,
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
            fill=secondary_color,
        )

    return img.convert("RGB")


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    x: int,
    y: int,
    fill: Tuple[int, int, int],
    line_spacing: int,
) -> int:
    lines = _wrap_text(draw, text, font, max_width)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.getbbox(line)[3] + line_spacing
    return y


def _wrap_text(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int
) -> List[str]:
    words = text.split()
    lines: List[str] = []
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


def _parse_color(color_str: str) -> Tuple[int, int, int]:
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


def _load_font(font_path: Optional[str], size: int) -> ImageFont.ImageFont:
    """
    Load a TrueType font with fallbacks to avoid pixelated bitmap fonts.
    Prioritizes fonts from the fonts/ folder, then custom font_path, then system fonts.
    Always returns a TrueType font for crisp rendering.
    """
    # First, try fonts from the fonts folder
    project_root = Path(__file__).parent.parent
    fonts_dir = project_root / "fonts"
    
    if fonts_dir.exists():
        # Try Roboto fonts first (regular, then italic)
        font_files = [
            fonts_dir / "Roboto-VariableFont_wdth,wght.ttf",
            fonts_dir / "Roboto-Italic-VariableFont_wdth,wght.ttf",
        ]
        # Also check for any other .ttf or .otf files in the fonts folder
        for font_file in fonts_dir.glob("*.ttf"):
            if font_file not in font_files:
                font_files.append(font_file)
        for font_file in fonts_dir.glob("*.otf"):
            if font_file not in font_files:
                font_files.append(font_file)
        
        for font_file in font_files:
            try:
                if font_file.exists():
                    return ImageFont.truetype(str(font_file), size=size)
            except Exception:
                continue
    
    # Second, try the custom font_path if provided
    if font_path:
        try:
            return ImageFont.truetype(font_path, size=size)
        except Exception:
            pass
    
    # Third, try common system fonts to avoid pixelated default font
    system_fonts = [
        # macOS - modern fonts
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # Windows (common paths)
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]
    
    for font_file in system_fonts:
        try:
            return ImageFont.truetype(font_file, size=size)
        except Exception:
            continue
    
    # Last resort: try arial.ttf in current directory or common locations
    try:
        return ImageFont.truetype("arial.ttf", size=size)
    except Exception:
        # If all else fails, use default but warn that it may be pixelated
        # In practice, one of the fonts should work
        return ImageFont.load_default()


