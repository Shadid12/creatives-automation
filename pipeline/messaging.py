from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class GeneratedMessaging:
    """
    Normalized messaging payload returned by the LLM (or mock).

    This is intentionally decoupled from any specific campaign schema so it can
    be reused across different pipelines.
    """

    headline: str
    description: Optional[str] = None
    call_to_action: Optional[str] = None


class MessagingGenerator:
    """
    Adapter for LLM-powered campaign messaging .
    """

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    def generate(
        self,
        *,
        campaign_name: str,
        brand_name: str,
        product: Dict[str, Any],
        locale: str,
        demographics: Optional[Dict[str, Any]] = None,
        existing_headline: Optional[str] = None,
        existing_description: Optional[str] = None,
        existing_cta: Optional[str] = None,
    ) -> GeneratedMessaging:
        """
        Produce messaging for a single product.

        - `demographics` and `locale` provide targeting + language context.
        - Existing messaging is treated as soft guidance / fallback.
        """
        demographics = demographics or {}

        if self.llm is None:
            raise RuntimeError(
                "MessagingGenerator.llm is None. Configure a real LLM instance "
                "before calling generate()."
            )

        prompt = self._build_prompt(
            campaign_name=campaign_name,
            brand_name=brand_name,
            product=product,
            locale=locale,
            demographics=demographics,
            existing_headline=existing_headline,
            existing_description=existing_description,
            existing_cta=existing_cta,
        )

        raw = self.llm.invoke(prompt)
        text = getattr(raw, "content", None) or str(raw)

        # We ask the model for a strict JSON object; if parsing fails we fall
        # back to the existing messaging values where available.
        import json

        try:
            payload = json.loads(text)
        except Exception:
            return GeneratedMessaging(
                headline=existing_headline or campaign_name,
                description=existing_description,
                call_to_action=existing_cta,
            )

        headline = (
            str(payload.get("headline")).strip()
            if payload.get("headline")
            else (existing_headline or campaign_name)
        )

        # Let the model generate the description as a punchy sales pitch that
        # leverages the provided demographics and locale. We rely primarily on
        # the model's `description` field here.
        description = str(payload.get("description") or "").strip()

        # CTA can still fall back to existing messaging if the model omits it.
        cta = (
            str(payload.get("call_to_action") or payload.get("cta") or existing_cta or "").strip()
        )

        return GeneratedMessaging(
            headline=headline,
            description=description or None,
            call_to_action=cta or None,
        )

    @staticmethod
    def _build_prompt(
        *,
        campaign_name: str,
        brand_name: str,
        product: Dict[str, Any],
        locale: str,
        demographics: Dict[str, Any],
        existing_headline: Optional[str],
        existing_description: Optional[str],
        existing_cta: Optional[str],
    ) -> str:
        """
        Construct a compact but richly structured system prompt.

        The LLM is instructed to respond *only* with a JSON object containing:
        - headline
        - description
        - call_to_action
        """
        product_name = product.get("name") or product.get("id") or ""
        product_description = product.get("description") or ""
        tags = product.get("tags") or []
        tag_str = ", ".join(tags)
        demo_str = ", ".join(f"{k}: {v}" for k, v in demographics.items())

        existing_parts = []
        if existing_headline:
            existing_parts.append(f'"headline": "{existing_headline}"')
        if existing_description:
            existing_parts.append(f'"description": "{existing_description}"')
        if existing_cta:
            existing_parts.append(f'"call_to_action": "{existing_cta}"')
        

        return (
            "You are an expert marketing copywriter generating ad copy for a multi-asset campaign.\n"
            f"- Write copy in locale: {locale}.\n"
            "- Use natural, fluent language for that locale. You should speak in a language that is appropriate for the target demographics.\n"
            "- Keep the headline punchy (max ~8 words) and benefit-driven.\n"
            "- Make the description a short, punchy sales pitch that clearly targets the given demographics and highlights product benefits.\n It should be 1-2 sentences long.\n"
            "- The call_to_action should be a short imperative phrase (e.g. 'Shop now').\n\n"
            "Context:\n"
            f'- Brand: "{brand_name}"\n'
            f'- Campaign: "{campaign_name}"\n'
            f'- Product name: "{product_name}"\n'
            f"- Product description: {product_description}\n"
            f"- Product tags: {tag_str or 'none'}\n"
            f"- Target demographics: {demo_str or 'unspecified'}\n\n"
            "Return ONLY a valid JSON object with this exact shape and no surrounding commentary:\n"
            '{\n'
            '  "headline": "string",\n'
            '  "description": "string",\n'
            '  "call_to_action": "string"\n'
            "}\n"
        )
