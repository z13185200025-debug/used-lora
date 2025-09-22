import json, os, sys
root = "data/fire-lora"
exts = {".png",".jpg",".jpeg",".webp",".bmp"}
meta = []
for dirpath,_,files in os.walk(root):
    for f in files:
        if os.path.splitext(f)[1].lower() in exts:
            img_rel = os.path.relpath(os.path.join(dirpath,f), root)
            stem = os.path.splitext(f)[0]
            # look for <stem>.txt or prompt.txt in same folder
            txt = None
            cand1 = os.path.join(dirpath, stem + ".txt")
            cand2 = os.path.join(dirpath, "prompt.txt")
            for c in (cand1, cand2):
                if os.path.exists(c):
                    with open(c, "r", encoding="utf-8", errors="ignore") as fh:
                        txt = fh.read().strip()
                    break
            if not txt:  # fallback: use folder name or stem
                txt = os.path.basename(dirpath).replace("_"," ")
            meta.append({"file_name": img_rel.replace("\\","/"), "text": txt})
out = os.path.join(root, "metadata.jsonl")
with open(out, "w", encoding="utf-8") as f:
    for m in meta:
        f.write(json.dumps(m, ensure_ascii=False) + "\n")
print(f"Wrote {len(meta)} entries to", out)