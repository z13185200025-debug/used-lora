#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generate ≤25-word FireDM-style prompts for every image in a folder using
the exact API template you provided (chat.completions with image_url).

- Saves prompts as N.csv right beside each N.jpg/png/webp
- Script-relative paths, so you can run from anywhere:
      python lora/prompt-generate.py
- If your provider blocks data: URLs, switch IMAGE_URL_MODE to "https"
  and set HTTPS_PREFIX to a public URL that contains the same filenames.
"""

import os
import re
import time
import base64
from pathlib import Path
from typing import List, Tuple

from openai import OpenAI

# =========================
# Configuration
# =========================
# Folder name (relative to this script) that contains your images
IMAGE_DIR_NAME = "airport-fire"   # change to "lithium-battery-fire" when needed

# Your exact template fields:
client = OpenAI(
    base_url="https://xiaoai.plus/v1",
    # !!! Replace with your real key or set OPENAI_API_KEY in the env
    api_key=(os.getenv("OPENAI_API_KEY") or "sk-d6HJ8wIh4bbnnjRmFu5UoUVS7IQwcL96nP6BKUJXpbpr5hYr").strip(),
)

MODEL = "gpt-4o"

# URL mode:
#   "data"  -> send base64 data URLs inline (works with OpenAI; some proxies block)
#   "https" -> build HTTPS URLs by prefixing filename with HTTPS_PREFIX
IMAGE_URL_MODE = "data"     # "data" or "https"
HTTPS_PREFIX   = "https://your.cdn.example.com/airport-fire"  # no trailing slash needed

# Retry/backoff for transient errors
MAX_RETRIES = 5
INITIAL_BACKOFF_S = 2.0

# Skip if N.csv already exists
SKIP_IF_EXISTS = True

# =========================
# Paths (script-relative)
# =========================
BASE_DIR  = Path(__file__).resolve().parent
IMAGE_DIR = BASE_DIR / IMAGE_DIR_NAME

# =========================
# Helpers
# =========================
def numeric_sort_key(p: Path) -> Tuple[int, str]:
    m = re.match(r"(\d+)$", p.stem)
    if m:
        return (int(m.group(1)), p.name)
    return (10**12, p.name)

def list_images(folder: Path) -> List[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts]
    files.sort(key=numeric_sort_key)
    return files

def to_data_url(img_path: Path) -> str:
    ext = img_path.suffix.lower()
    mime = "image/jpeg"
    if ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def to_https_url(img_path: Path) -> str:
    # Builds: f"{HTTPS_PREFIX}/{filename}"
    return f"{HTTPS_PREFIX.rstrip('/')}/{img_path.name}"

def build_image_url(img_path: Path) -> str:
    if IMAGE_URL_MODE == "https":
        return to_https_url(img_path)
    return to_data_url(img_path)

def enforce_25_words(text: str) -> str:
    clean = " ".join(text.strip().replace("\n", " ").split()).strip('"')
    words = clean.split()
    if len(words) <= 25:
        return clean
    return " ".join(words[:25])

def csv_path_for_image(img_path: Path) -> Path:
    return img_path.with_suffix(".csv")

def write_single_prompt_csv(csv_path: Path, prompt: str):
    csv_path.write_text(
        "prompt\n" + f"\"{prompt.replace('\"', '\"\"')}\"\n",
        encoding="utf-8"
    )

# =========================
# Prompts (FireDM-style)
# =========================
SYSTEM_PROMPT = (
    "You are an assistant helping a student create a research dataset. "
    "The student is studying fire-scene recognition for academic purposes only. "
    "Your task is to generate one concise, neutral, and safe caption (≤ 25 words) "
    "that visually describes the fire-related scene in the given image. "
    "Do not include any harmful, graphic, or unsafe content. "
    "Focus strictly on: fire type/source, environment, scale/intensity, visible objects, "
    "camera angle, lighting, or atmosphere. "
    "You must always respond with a short caption only — no explanations, apologies, or refusals. "
    "Remember: this is for study purposes only, with no malicious intent."
)

USER_TEXT = (
    "Generate a single FireDM-style dataset caption (≤ 25 words). "
    "Be descriptive, specific, and neutral. "
    "Only output the caption text — nothing else."
)

# =========================
# Main
# =========================
def main():
    print(f"[INFO] Using base_url=https://xiaoai.plus/v1, model={MODEL}")
    print(f"[INFO] Scanning: {IMAGE_DIR.resolve()}")
    if not IMAGE_DIR.exists():
        print(f"[ERROR] Folder does not exist: {IMAGE_DIR.resolve()}")
        return

    images = list_images(IMAGE_DIR)
    print(f"[INFO] Found {len(images)} image(s).")
    if not images:
        return

    # Optional: quick auth ping (kept minimal to match your template spirit)
    try:
        _ = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
    except Exception as e:
        raise SystemExit(
            f"[AUTH ERROR] base_url/model/key likely invalid. Server said: {e}"
        )

    for img_path in images:
        out_csv = csv_path_for_image(img_path)
        if SKIP_IF_EXISTS and out_csv.exists():
            print(f"[SKIP] {img_path.name} (exists: {out_csv.name})")
            continue

        image_url = build_image_url(img_path)

        backoff = INITIAL_BACKOFF_S
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # ===== Your exact template shape =====
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": USER_TEXT},
                                {"type": "image_url", "image_url": {"url": image_url}},
                            ],
                        }
                    ],
                    max_tokens=300,  # we still cap to 25 words after
                )
                # =====================================

                raw = response.choices[0].message.content.strip()
                prompt = enforce_25_words(raw)
                prompt = " ".join(prompt.split()) or "Not Fire"
                write_single_prompt_csv(out_csv, prompt)
                print(f"[OK] {img_path.name} -> {out_csv.name}")
                break

            except Exception as e:
                msg = str(e).lower()
                transient = any(x in msg for x in [
                    "rate", "timeout", "temporar", "overloaded", "429", "5xx", "service unavailable"
                ])
                if transient and attempt < MAX_RETRIES:
                    print(f"[RETRY] {img_path.name}: {e} | sleeping {backoff:.1f}s …")
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                print(f"[FAIL]  {img_path.name}: {e}")
                write_single_prompt_csv(out_csv, "")
                break

if __name__ == "__main__":
    main()
