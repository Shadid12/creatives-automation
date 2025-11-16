from pathlib import Path
from typing import Dict, Optional

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def find_existing_asset_for_product(
    product: Dict,
    campaign_id: str,
    assets_dir: Path,
) -> Optional[Path]:
    """
    Try to locate a reusable asset for a product in the input-assets folder.

    Search heuristics (in order):
    - explicit `asset_path` on the product (relative to assets_dir)
    - files containing the product id / sku / name (slugged) in their filename
    - files containing the campaign_id and product id
    """
    if not assets_dir.exists():
        return None

    explicit_path = product.get("asset_path")
    if explicit_path:
        candidate = assets_dir / explicit_path
        if candidate.exists():
            return candidate

    product_id = str(product.get("id") or product.get("sku") or product.get("name") or "")
    if not product_id:
        return None

    product_slug = _slugify(product_id)

    best_match: Optional[Path] = None
    for path in assets_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        name = path.stem.lower()
        if product_slug in name:
            best_match = path
            break
        if campaign_id.lower() in name and product_slug in name:
            best_match = path
            break

    return best_match


def _slugify(text: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "item"


