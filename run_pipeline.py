import argparse
import os
from pathlib import Path
from langchain_openai import ChatOpenAI

from dotenv import load_dotenv

from pipeline.core import CreativePipeline
from pipeline.messaging import MessagingGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the local creative automation pipeline for a campaign brief."
    )
    parser.add_argument(
        "--brief",
        type=Path,
        required=True,
        help="Path to the campaign brief JSON file.",
    )
    parser.add_argument(
        "--input-assets",
        type=Path,
        required=True,
        help="Path to the folder containing pre-provided assets.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("outputs"),
        help="Root folder where generated creatives will be stored.",
    )
    return parser.parse_args()


def main() -> None:
    # Load environment variables from a local .env file if present
    # (e.g. OPENAI_API_KEY=sk-...).
    load_dotenv()

    args = parse_args()

    # Configure messaging LLM (OpenAI via LangChain) based on environment.
    # If OPENAI_API_KEY is defined, we use a real LLM; otherwise we fall back
    # to the local deterministic mock (no network calls).
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        llm = ChatOpenAI(
            model="gpt-5-mini-2025-08-07",
            temperature=0.9,
            api_key=api_key,
        )
        # When an API key is present, use the real image generator as well.
        use_mock = False
    else:
        # Explicitly pass None to enable the local mock behavior inside
        # MessagingGenerator when no real LLM is configured, and use the
        # local mock image generator.
        llm = None
        use_mock = True

    messaging_generator = MessagingGenerator(llm=llm)

    pipeline = CreativePipeline(
        input_assets_dir=args.input_assets,
        output_root=args.output_root,
        use_mock_generator=use_mock,
        messaging_generator=messaging_generator,
    )
    pipeline.run(args.brief)


if __name__ == "__main__":
    main()


