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

        # Also load the raw JSON so we can persist any newly generated asset paths.
        with brief_path.open("r", encoding="utf-8") as f:
            brief_data = json.load(f)

        campaign_root = self.output_root / brief.campaign_id
        campaign_root.mkdir(parents=True, exist_ok=True)

        products_data = brief_data.get("products", [])
        brief_updated = False

        for idx, product in enumerate(brief.products):
            product_id = str(product.get("id") or product.get("sku") or product.get("name"))
            product_slug = _slugify(product_id)

            # Generate messaging once per product; reused across all aspect ratios.
            product_messaging = self._build_messaging_for_product(brief, product)

            # 1) Re-use asset if available. If not, generate a new image (via Replicate
            # when configured) and persist it under input-assets, then update the brief.
            asset_path = find_existing_asset_for_product(
                product=product,
                campaign_id=brief.campaign_id,
                assets_dir=self.input_assets_dir,
            )

            if asset_path is None:
                # Product has no asset_path field - generate new image
                print(f"🎨 Generating image for product '{product_id}' (no asset_path found)")
                prompt = self._build_image_prompt_for_product(brief, product)
                base_img = self.generator.generate_image(prompt=prompt)

                # Persist the generated base asset so it can be reused across runs.
                self.input_assets_dir.mkdir(parents=True, exist_ok=True)
                asset_filename = f"{product_slug}.png"
                asset_full_path = self.input_assets_dir / asset_filename
                base_img.save(asset_full_path, format="PNG")

                # Update in-memory product dict
                product["asset_path"] = asset_filename
                # Update the raw JSON data, if a corresponding entry exists
                if 0 <= idx < len(products_data):
                    products_data[idx]["asset_path"] = asset_filename
                    brief_data["products"] = products_data
                    brief_updated = True

                asset_path = asset_full_path
            else:
                # Product has asset_path field - use existing image
                print(f"📁 Loading existing asset for product '{product_id}' from: {asset_path.name}")
                base_img = self.generator.load_existing_image(asset_path)

            for aspect_key, target_ratio in ASPECT_RATIOS.items():
                out_dir = campaign_root / product_slug / aspect_key.replace(":", "x")
                out_dir.mkdir(parents=True, exist_ok=True)

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

        # Persist any new asset paths back to the brief JSON file.
        if brief_updated:
            with brief_path.open("w", encoding="utf-8") as f:
                json.dump(brief_data, f, indent=2, ensure_ascii=False)

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
    def _build_image_prompt_for_product(
        brief: CampaignBrief,
        product: Dict,
    ) -> str:
        """
        Build an image-generation prompt that uses product name, description,
        and campaign demographics to create an advertising image.
        """
        name = product.get("name", "a product")
        description = product.get("description") or ""
        tags = product.get("tags") or []
        tag_str = ", ".join(tags) if tags else ""

        demographics = brief.demographics or {}
        if demographics:
            demo_parts = [f"{k}: {v}" for k, v in demographics.items()]
            demo_str = "; ".join(demo_parts)
        else:
            demo_str = "General active lifestyle audience"

        prompt = (
            f"High-quality advertising product photo for the brand {brief.brand_name}. "
            f"Product name: {name}. "
            f"Product description: {description}. "
            f"Target demographic: {demo_str}. "
        )

        if tag_str:
            prompt += f"Keywords and visual cues: {tag_str}. "

        prompt += (
            "Style: clean, modern commercial photography, well-lit, realistic, "
            "studio-quality composition suitable for digital marketing creatives."
        )

        return prompt


def _slugify(text: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "item"


