import csv
import sys
from pathlib import Path
import re

PROMPT_COL_CANDIDATES = [
    "prompt", "caption", "text", "description", "desc",
    "prompt_text", "caption_text", "prompttext", "captiontext",
]

_CONTROL_CHARS_RE = re.compile(r"[\u0000-\u001F\u007F]")  # strip ASCII control chars
_WS_RE = re.compile(r"\s+")


def _clean(s: str) -> str:
    if s is None:
        return ""
    # remove zero-width + control chars; normalize whitespace; strip quotes/brackets around single-field exports
    s = s.replace("\ufeff", "")  # BOM
    s = _CONTROL_CHARS_RE.sub("", s)
    s = s.strip()
    # de-wrap if it's quoted as a whole cell
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        s = s[1:-1].strip()
    # collapse excessive whitespace
    s = _WS_RE.sub(" ", s)
    return s


def _looks_like_prompt(text: str) -> bool:
    """Heuristic to prefer actual natural-language prompts over short tokens."""
    if not text:
        return False
    # Length and character heuristics
    if len(text) < 8:
        return False
    # has spaces or punctuation typical of sentences
    if " " in text or any(p in text for p in [",", ".", ":", ";", "!", "?"]):
        return True
    # avoid picking filenames or tiny labels
    if re.search(r"\.(png|jpg|jpeg|webp|gif|txt|csv)$", text, re.I):
        return False
    return len(text) >= 12


def extract_prompt(csv_path: Path) -> str:
    # Read the whole file once for sniffer + reuse
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        raw = f.read()

    if not raw.strip():
        return ""

    # Sniff dialect & header
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(raw)
    except Exception:
        dialect = csv.excel

    try:
        has_header = csv.Sniffer().has_header(raw)
    except Exception:
        has_header = True  # many tools emit a header; defaulting to True is safer for your case

    # Re-parse with the chosen dialect
    lines = [ln for ln in raw.splitlines() if ln.strip()]  # drop empty lines
    if not lines:
        return ""

    # If header: use DictReader and target a prompt-like column
    if has_header:
        reader = csv.DictReader(lines, dialect=dialect)
        # normalize fieldnames
        field_map = {}
        for fn in (reader.fieldnames or []):
            norm = _clean(fn).lower().replace(" ", "").replace("-", "").replace("_", "")
            field_map[norm] = fn

        # pick best candidate column name
        chosen_field = None
        for cand in PROMPT_COL_CANDIDATES:
            key = cand.lower().replace(" ", "").replace("-", "").replace("_", "")
            if key in field_map:
                chosen_field = field_map[key]
                break

        # Fallback: if nothing matched, choose the **longest textual** column from the first data row
        first_row = next(iter(reader), None)
        if first_row is None:
            return ""

        if not chosen_field:
            # find the most "prompty" cell
            candidates = []
            for k, v in first_row.items():
                v_clean = _clean(v or "")
                if _looks_like_prompt(v_clean):
                    candidates.append((len(v_clean), v_clean))
            if candidates:
                return max(candidates, key=lambda x: x[0])[1]
            # final fallback: longest non-empty
            longest = max((_clean(v or "") for v in first_row.values()), key=len, default="")
            return longest

        # If we have a chosen prompt column, return first non-empty value from it
        val = _clean(first_row.get(chosen_field) or "")
        if val:
            return val
        # else scan remaining rows for first non-empty
        for row in reader:
            v = _clean(row.get(chosen_field) or "")
            if v:
                return v
        return ""

    # No header: treat as plain rows; pick a "prompty" field from the first non-empty row
    reader = csv.reader(lines, dialect=dialect)
    for row in reader:
        cells = [_clean(c) for c in row if _clean(c)]
        if not cells:
            continue
        prompty = [c for c in cells if _looks_like_prompt(c)]
        if prompty:
            # prefer the longest plausible prompt
            return max(prompty, key=len)
        # fallback: longest non-empty cell
        return max(cells, key=len)
    return ""


def process_dir(root: Path):
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    for img in root.iterdir():
        if img.suffix.lower() not in exts:
            continue
        csvp = img.with_suffix(".csv")
        if not csvp.exists():
            continue
        prompt = extract_prompt(csvp)
        img.with_suffix(".txt").write_text(prompt, encoding="utf-8")
        print(f"[OK] {img.name} -> {img.with_suffix('.txt').name}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/csv_to_txt_captions.py <dir1> [<dir2> ...]")
        sys.exit(1)
    for p in sys.argv[1:]:
        process_dir(Path(p))
