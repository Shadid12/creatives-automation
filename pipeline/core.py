import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional

from .assets import find_existing_asset_for_product
from .generator import ImageGenerator
from .render import (
    ASPECT_RATIOS,
    overlay_campaign_text,
    resize_to_aspect_ratio,
)


AspectKey = Literal["1:1", "9:16", "16:9"]


@dataclass
class CampaignMessaging:
    headline: str
    subheading: Optional[str] = None
    call_to_action: Optional[str] = None


@dataclass
class CampaignBrief:
    campaign_id: str
    campaign_name: str
    brand_name: str
    primary_color: str
    messaging: CampaignMessaging
    products: List[Dict]
    font_path: Optional[str] = None


def load_brief(path: Path) -> CampaignBrief:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    messaging = data.get("messaging", {})
    return CampaignBrief(
        campaign_id=data["campaign_id"],
        campaign_name=data["campaign_name"],
        brand_name=data["brand_name"],
        primary_color=data.get("primary_color", "#111827"),
        messaging=CampaignMessaging(
            headline=messaging.get("headline", data["campaign_name"]),
            subheading=messaging.get("subheading"),
            call_to_action=messaging.get("call_to_action"),
        ),
        font_path=data.get("font_path"),
        products=data.get("products", []),
    )


class CreativePipeline:
    """
    Orchestrates the creative generation pipeline:
    - load brief
    - for each product and aspect ratio:
        * reuse input asset if available
        * otherwise call the (mock) GenAI generator
        * resize and render campaign messaging
        * save under outputs/{campaign_id}/{product_slug}/{aspect}/
    """

    def __init__(
        self,
        input_assets_dir: Path,
        output_root: Path,
        use_mock_generator: bool = True,
    ) -> None:
        self.input_assets_dir = input_assets_dir
        self.output_root = output_root
        self.generator = ImageGenerator(use_mock=use_mock_generator)

    def run(self, brief_path: Path) -> None:
        brief = load_brief(brief_path)
        campaign_root = self.output_root / brief.campaign_id
        campaign_root.mkdir(parents=True, exist_ok=True)

        for product in brief.products:
            product_id = str(product.get("id") or product.get("sku") or product.get("name"))
            product_slug = _slugify(product_id)

            for aspect_key, target_ratio in ASPECT_RATIOS.items():
                out_dir = campaign_root / product_slug / aspect_key.replace(":", "x")
                out_dir.mkdir(parents=True, exist_ok=True)

                # 1) re-use asset if available
                asset_path = find_existing_asset_for_product(
                    product=product,
                    campaign_id=brief.campaign_id,
                    assets_dir=self.input_assets_dir,
                )

                if asset_path is not None:
                    base_img = self.generator.load_existing_image(asset_path)
                else:
                    prompt = self._build_prompt(brief, product, aspect_key)
                    base_img = self.generator.generate_image(prompt=prompt)

                resized = resize_to_aspect_ratio(base_img, target_ratio)
                rendered = overlay_campaign_text(
                    resized,
                    campaign=brief,
                    product=product,
                )

                filename = f"{brief.campaign_id}_{product_slug}_{aspect_key.replace(':', 'x')}.png"
                output_path = out_dir / filename
                rendered.save(output_path, format="PNG")

    @staticmethod
    def _build_prompt(
        brief: CampaignBrief, product: Dict, aspect_key: AspectKey
    ) -> str:
        description = product.get("description") or product.get("name") or ""
        tags = product.get("tags") or []
        tag_str = ", ".join(tags)
        return (
            f"Product photo of {product.get('name', 'a product')} "
            f"for brand {brief.brand_name}. "
            f"Style: clean, modern advertising. "
            f"Aspect ratio {aspect_key}. "
            f"Details: {description}. "
            f"Keywords: {tag_str}."
        )


def _slugify(text: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "item"


