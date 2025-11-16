import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional

from .assets import find_existing_asset_for_product
from .generator import ImageGenerator
from .messaging import GeneratedMessaging, MessagingGenerator
from .render import (
    ASPECT_RATIOS,
    overlay_campaign_text,
    resize_to_aspect_ratio,
)


AspectKey = Literal["1:1", "9:16", "16:9"]


@dataclass
class CampaignMessaging:
    headline: str
    # `description` is the canonical field name going forward.
    # `subheading` is kept as a backwards-compatible alias (property below).
    description: Optional[str] = None
    call_to_action: Optional[str] = None

    # Backwards-compatible alias so existing code that references
    # `messaging.subheading` continues to work.
    @property
    def subheading(self) -> Optional[str]:
        return self.description


@dataclass
class CampaignBrief:
    campaign_id: str
    campaign_name: str
    brand_name: str
    primary_color: str
    secondary_color: str
    messaging: CampaignMessaging
    products: List[Dict]
    locale: str = "en-US"
    demographics: Optional[Dict] = None
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
        secondary_color=data.get("secondary_color", "#F97316"),
        messaging=CampaignMessaging(
            headline=messaging.get("headline", data["campaign_name"]),
            description=messaging.get("description") or messaging.get("subheading"),
            call_to_action=messaging.get("call_to_action"),
        ),
        products=data.get("products", []),
        locale=data.get("locale", "en-US"),
        demographics=data.get("demographics") or {},
        font_path=data.get("font_path"),
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
        messaging_generator: Optional[MessagingGenerator] = None,
    ) -> None:
        self.input_assets_dir = input_assets_dir
        self.output_root = output_root
        self.generator = ImageGenerator(use_mock=use_mock_generator)
        # LLM-backed messaging generator (defaults to local mock implementation).
        self.messaging_generator = messaging_generator or MessagingGenerator()

    def run(self, brief_path: Path) -> None:
        brief = load_brief(brief_path)
        campaign_root = self.output_root / brief.campaign_id
        campaign_root.mkdir(parents=True, exist_ok=True)

        for product in brief.products:
            product_id = str(product.get("id") or product.get("sku") or product.get("name"))
            product_slug = _slugify(product_id)

            # Generate messaging once per product; reused across all aspect ratios.
            product_messaging = self._build_messaging_for_product(brief, product)

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
                    messaging=product_messaging,
                )

                filename = f"{brief.campaign_id}_{product_slug}_{aspect_key.replace(':', 'x')}.png"
                output_path = out_dir / filename
                rendered.save(output_path, format="PNG")

    def _build_messaging_for_product(
        self,
        brief: CampaignBrief,
        product: Dict,
    ) -> CampaignMessaging:
        """
        Use the LLM adapter to generate product-level messaging for the campaign.

        This keeps the pipeline text-generation logic centralized and makes it
        easy to swap in a real LLM via `MessagingGenerator`.
        """
        generated: GeneratedMessaging = self.messaging_generator.generate(
            campaign_name=brief.campaign_name,
            brand_name=brief.brand_name,
            product=product,
            locale=brief.locale,
            demographics=brief.demographics or {},
            existing_headline=brief.messaging.headline,
            existing_description=brief.messaging.description,
            existing_cta=brief.messaging.call_to_action,
        )

        return CampaignMessaging(
            headline=generated.headline or brief.messaging.headline,
            description=generated.description or brief.messaging.description,
            call_to_action=generated.call_to_action or brief.messaging.call_to_action,
        )

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


