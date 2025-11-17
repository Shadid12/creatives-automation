# Creative Automation Pipeline

A **local, deterministic creative automation pipeline** for generating product marketing creatives at scale. This system takes a campaign brief with product information and automatically generates branded visuals in multiple aspect ratios for different platforms (social media, web, etc.).

## Features

- **Multi-format output**: Generates creatives in 1:1, 9:16, and 16:9 aspect ratios
- **Asset reuse**: Automatically finds and reuses existing product images from your asset library
- **AI-powered generation**: Optionally generates product images using AI when assets aren't available
- **Localization support**: Adapts messaging for different locales (e.g., en-US, es-ES)
- **LLM messaging**: Generates contextual campaign messaging using LangChain + OpenAI

## Requirements

- Python 3.10 or higher
- (Optional) OpenAI API key for LLM-based messaging generation
- (Optional) Replicate API key for AI image generation

## Installation

### 1. Set up Python environment

Using `pyenv` (recommended):

```bash
# Install pyenv if you haven't already
brew install pyenv  # macOS
# or follow instructions at https://github.com/pyenv/pyenv

# Install Python 3.10+
pyenv install 3.10.13
pyenv local 3.10.13
```

Using system Python:

```bash
# Verify Python version
python3 --version  # Should be 3.10 or higher
```

### 2. Create and activate virtual environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. (Optional) Configure API keys

Create a `.env` file in the project root:

```bash
# For LLM-based messaging generation
OPENAI_API_KEY=sk-...

# For AI image generation (if not using existing assets)
REPLICATE_API_TOKEN=r8_...
```

**Note**: If you don't provide API keys, the pipeline will use local mock generators (deterministic, no network calls).

## Usage

### Basic command

```bash
python run_pipeline.py \
  --brief examples/product_sample.json \
  --input-assets examples/input_assets \
  --output-root outputs
```

### Command-line arguments

- `--brief`: Path to campaign brief JSON file (required)
- `--input-assets`: Path to folder containing product images (required)
- `--output-root`: Root folder for generated creatives (default: `outputs`)

### Example briefs

The `examples/` directory contains sample campaign briefs:

- `product_sample.json`: Standard campaign with existing product images
- `product_sample_no_img.json`: Campaign requiring AI image generation
- `product_sample_esp.json`: Spanish localization example

## Campaign Brief Format

```json
{
  "campaign_id": "fall_launch_2025",
  "campaign_name": "Fall Launch 2025",
  "brand_name": "Northwind Athletics",
  "primary_color": "#F97316",
  "secondary_color": "#FFFFFF",
  "font_path": "fonts/Roboto-VariableFont_wdth,wght.ttf",
  "messaging": {
    "headline": "Move Faster This Fall",
    "subheading": "Lightweight performance gear designed for cooler days.",
    "call_to_action": "Shop the Fall Drop"
  },
  "locale": "en-US",
  "demographics": {
    "gender": "Female",
    "age": "25-34",
    "location": "United States - California - West Coast"
  },
  "products": [
    {
      "id": "trail-runner-shoe",
      "name": "Trail Runner Shoe",
      "description": "Engineered for aggressive trail conditions...",
      "tags": ["running", "trail", "outdoor"],
      "asset_path": "trail-runner-shoe.png"
    }
  ]
}
```

## Project Structure

```
creative-automation/
├── pipeline/              # Core pipeline modules
│   ├── core.py           # Main pipeline orchestration
│   ├── assets.py         # Asset management and lookup
│   ├── generator.py      # Image generation (AI + mock)
│   ├── messaging.py      # LLM-based messaging generation
│   └── render.py         # Image composition and text overlay
├── examples/             # Sample campaign briefs and assets
│   ├── input_assets/     # Example product images
│   └── *.json           # Sample campaign briefs
├── fonts/                # Typography assets
├── outputs/              # Generated creatives (created at runtime)
├── run_pipeline.py       # Main entry point
└── requirements.txt      # Python dependencies
```

## How It Works

1. **Load Brief**: Reads campaign configuration and product list
2. **Asset Discovery**: Searches for existing product images in the input assets directory
3. **Image Generation**: If no asset found, generates product image using AI (or mock)
4. **Messaging Adaptation**: Uses LLM to adapt campaign messaging for each product and locale
5. **Creative Generation**: For each product and aspect ratio:
   - Resizes product image to target dimensions
   - Overlays campaign text with brand colors
   - Saves to structured output directory
6. **Output Organization**: Creates directory structure: `{campaign_id}/{product_id}/{aspect_ratio}/`

## Output Structure

Generated creatives are organized as:

```
outputs/
└── fall_launch_2025/
    ├── trail-runner-shoe/
    │   ├── 1x1/
    │   │   └── fall_launch_2025_trail-runner-shoe_1x1.png
    │   ├── 9x16/
    │   │   └── fall_launch_2025_trail-runner-shoe_9x16.png
    │   └── 16x9/
    │       └── fall_launch_2025_trail-runner-shoe_16x9.png
    └── thermal-joggers/
        ├── 1x1/
        ├── 9x16/
        └── 16:9/
```