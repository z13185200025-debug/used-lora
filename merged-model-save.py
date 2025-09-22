import torch
from diffusers import StableDiffusionPipeline

base = "stabilityai/stable-diffusion-2-1-base"
pipe = StableDiffusionPipeline.from_pretrained(base, torch_dtype=torch.float16)
pipe.load_lora_weights("runs/lora_sd21_fire")
pipe.fuse_lora()
pipe.save_pretrained("models/sd21_fire_merged")
print("Saved to models/sd21_fire_merged")