import argparse
from pathlib import Path

from pipeline.core import CreativePipeline


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
    parser.add_argument(
        "--use-mock-generator",
        action="store_true",
        help="Force using the local mock GenAI image generator (default).",
    )
    parser.add_argument(
        "--use-real-generator",
        action="store_true",
        help="Placeholder flag for wiring a real GenAI generator in the future.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.use_real_generator and args.use_mock_generator:
        raise SystemExit("Choose either --use-real-generator or --use-mock-generator, not both.")

    use_mock = not args.use_real_generator

    pipeline = CreativePipeline(
        input_assets_dir=args.input_assets,
        output_root=args.output_root,
        use_mock_generator=use_mock,
    )
    pipeline.run(args.brief)


if __name__ == "__main__":
    main()


