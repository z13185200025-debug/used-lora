# Fire Scene LoRA Fine-Tuning

This project prepares a small fire-scene image dataset and fine-tunes a Stable Diffusion 2.1 LoRA for generating realistic fire emergency scenes, including airport runway fires and lithium battery fire scenarios.

The repository includes:

- Fire image datasets with paired CSV/TXT captions
- Caption conversion utilities
- A Hugging Face Diffusers LoRA training script
- Example training, inference, and model-merging commands

## Project Structure

```text
.
|-- airport-fire/                  # Airport fire images and captions
|-- lithium-battery-fire/          # Lithium battery fire images and captions
|-- data/fire-lora/                # Combined training dataset
|-- scripts/train_text_to_image_lora.py
|-- tools/csv_to_txt_captions.py   # Converts CSV prompts to .txt captions
|-- prepare.py                     # Builds metadata.jsonl from image/text pairs
|-- prompt-generate.py             # Generates captions with a vision model
|-- merged-model-save.py           # Merges LoRA weights into the base model
|-- qick-run.txt                   # End-to-end quick-start command reference
`-- run-command.txt                # Training command reference
```

## Requirements

Use a CUDA-capable environment for training.

```bash
conda create -n sd21-lora python=3.10 -y
conda activate sd21-lora

pip install --upgrade \
  torch torchvision \
  diffusers transformers accelerate datasets peft safetensors pillow xformers
```

If you need the exact versions used during development, see `environment.txt`.

## Dataset Preparation

Each image should have a matching caption file with the same stem:

```text
1.jpg
1.csv
1.txt
```

Convert CSV prompt files into TXT captions:

```bash
python tools/csv_to_txt_captions.py airport-fire lithium-battery-fire
```

Build the combined training folder:

```bash
mkdir -p data/fire-lora
cp airport-fire/* data/fire-lora/
cp lithium-battery-fire/* data/fire-lora/
```

Generate `metadata.jsonl` for Diffusers dataset loading:

```bash
python prepare.py
```

## Training

Configure Accelerate once:

```bash
accelerate config default
```

Start LoRA training:

```bash
accelerate launch scripts/train_text_to_image_lora.py \
  --pretrained_model_name_or_path="stabilityai/stable-diffusion-2-1-base" \
  --train_data_dir="data/fire-lora" \
  --resolution=512 --center_crop --random_flip \
  --train_batch_size=4 --gradient_accumulation_steps=4 \
  --gradient_checkpointing \
  --learning_rate=1e-4 --lr_scheduler="cosine" --lr_warmup_steps=200 \
  --max_train_steps=6000 --mixed_precision="bf16" \
  --checkpointing_steps=1000 \
  --validation_prompt="airport fire on runway, foam suppression, thick smoke, realistic, cinematic lighting" \
  --num_validation_images=4 \
  --validation_epochs=1 \
  --seed=42 \
  --output_dir="runs/lora_sd21_fire"
```

Training artifacts are written to:

```text
runs/lora_sd21_fire/
```

## Inference

Generate a sample image with the trained LoRA:

```bash
python - <<'PY'
import torch
from diffusers import StableDiffusionPipeline

pipe = StableDiffusionPipeline.from_pretrained(
    "stabilityai/stable-diffusion-2-1-base",
    torch_dtype=torch.float16,
).to("cuda")

pipe.load_lora_weights("runs/lora_sd21_fire")

image = pipe(
    "lithium battery fire in workshop, thermal runaway, realistic, cinematic",
    num_inference_steps=30,
    guidance_scale=7.5,
).images[0]

image.save("sample_fire.png")
print("Saved sample_fire.png")
PY
```

## Merge LoRA Weights

To save a merged Stable Diffusion pipeline:

```bash
python merged-model-save.py
```

The merged model is saved to:

```text
models/sd21_fire_merged/
```

## Prompt Generation

`prompt-generate.py` can create concise fire-scene captions for images using a vision-language API. Before running it:

1. Set your API key in the environment:

   ```bash
   export OPENAI_API_KEY="your_api_key_here"
   ```

2. Update `IMAGE_DIR_NAME` in `prompt-generate.py` if you want to caption a different folder.

3. Run:

   ```bash
   python prompt-generate.py
   ```

The script writes one CSV caption file beside each image.

## Notes

- Keep training prompts concise and visually grounded.
- Keep image/caption filenames aligned by stem, for example `8.jpg`, `8.csv`, and `8.txt`.
- Do not commit private API keys or generated model checkpoints unless they are intentionally shared.
- `qick-run.txt` contains the original compact end-to-end command sequence.
