#!/usr/bin/env python3
"""
Refresh the Galley data file.

Pipeline role: the ONLY thing that changes on a cadence. It asks Claude to
re-research current GF/DF products (availability, swaps, fresh rotation) and
emit a complete data file matching schema/galley.schema.json. Output is
validated and referential-integrity-checked; the file is published only if it
passes. On any failure the previous good file is left untouched.

Env:
  ANTHROPIC_API_KEY   required
  GALLEY_MODEL        optional, default 'claude-sonnet-4-6'
  GALLEY_DATA         optional, default 'data/galley-data.json'
  GALLEY_SCHEMA       optional, default 'schema/galley.schema.json'

Usage:
  python scripts/generate.py            # refresh in place (atomic, validated)
  python scripts/generate.py --check    # validate the existing file only, no API call
  python scripts/generate.py --dry-run  # call API + validate, print, do NOT write
"""

import argparse
import datetime
import json
import os
import sys
import tempfile

import jsonschema

try:
    import anthropic
except ImportError:
    anthropic = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, os.environ.get("GALLEY_DATA", "data/galley-data.json"))
SCHEMA = os.path.join(
    ROOT, os.environ.get("GALLEY_SCHEMA", "schema/galley.schema.json")
)
MODEL = os.environ.get("GALLEY_MODEL", "claude-sonnet-4-6")

# How much of the existing file the model may rewrite. Structure (slots/macros/
# appliances/effort) is the carefully-tuned part we DON'T want drifting weekly,
# so the prompt asks Claude to keep the meal engineering and only refresh the
# product picks + verify availability. Everything is re-validated regardless.
SYSTEM = """You maintain a gluten-free, dairy-free meal-and-grocery data file for one person.
Hard constraints you must preserve:
- Every food item must be plausibly gluten-free AND dairy-free.
- Keep daily plans roughly 2,400-3,200 kcal and at least ~175g protein/day.
- Keep the low-active-effort design: meals use rice cooker / Instant Pot / air fryer /
  crockpot / microwave / blender / no-cook only. No stovetop-heavy, multi-step dishes.
- Preserve the JSON structure and all keys EXACTLY as in the schema. Do not invent new top-level keys.
You may: refresh snack/entree product picks in `catalog`, swap a product that looks
discontinued for a current GF/DF equivalent, refresh the rotation ordering, and bump
`updated`. Do NOT redesign macros, appliances, or active-minute values.
Return ONLY the complete JSON object, no prose, no markdown fences."""


def load(p):
    with open(p) as f:
        return json.load(f)


def validate(data, schema):
    jsonschema.validate(data, schema)
    cat, meals = set(data["catalog"]), set(data["meals"])
    errs = []
    for wk in ("A", "B"):
        for d_i, day in enumerate(data["plan"][wk]):
            for sid in day:
                if sid not in cat and sid not in meals:
                    errs.append(f"plan {wk} day{d_i}: unknown id '{sid}'")
    for w_i, w in enumerate(data["rotation"]):
        for sid in w["entrees"] + w["snacks"]:
            if sid not in cat:
                errs.append(f"rotation week{w_i}: unknown catalog id '{sid}'")
    for wk in ("A", "B"):
        for c in data["shop"][wk]["cats"]:
            for it in c["items"]:
                if "ref" in it and it["ref"] not in cat:
                    errs.append(f"shop {wk}: unknown ref '{it['ref']}'")
    if errs:
        raise ValueError("referential integrity failed:\n  " + "\n  ".join(errs))


def ask_claude(current, schema):
    if anthropic is None:
        sys.exit("anthropic package not installed: pip install anthropic")
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    prompt = (
        "Here is the current data file. Verify the packaged products are still sold and "
        "still gluten-free + dairy-free (search the web), swap any that look discontinued for "
        "a current GF/DF equivalent, give the rotation a fresh ordering, set `updated` to today ("
        + datetime.date.today().isoformat()
        + "), and return the COMPLETE updated JSON.\n\n"
        "Current file:\n" + json.dumps(current)
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=32000,
        system=SYSTEM,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
        messages=[{"role": "user", "content": prompt}],
    )
    block_types = [b.type for b in resp.content]
    print(f"stop_reason={resp.stop_reason} blocks={block_types}")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError(
            "API response hit max_tokens limit — output was truncated. "
            "Increase max_tokens or reduce input size."
        )
    # concatenate the text blocks (tool_use / server tool blocks are skipped)
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if not text:
        raise RuntimeError(
            f"API returned no text block. stop_reason={resp.stop_reason!r}, "
            f"block types present: {block_types}"
        )
    # strip markdown fences if present
    if "```" in text:
        parts = text.split("```")
        # odd-indexed parts are inside fences
        for part in parts[1::2]:
            candidate = part.lstrip("json").strip()
            if candidate.startswith("{"):
                text = candidate
                break
    # skip any prose the model emitted before the JSON object
    brace = text.find("{")
    if brace == -1:
        raise RuntimeError(
            f"No JSON object found in response. "
            f"stop_reason={resp.stop_reason!r}. "
            f"First 500 chars: {text[:500]!r}"
        )
    text = text[brace:]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"JSON parse failed: {exc}. "
            f"First 300 chars of extracted text: {text[:300]!r}"
        ) from exc


def atomic_write(path, data):
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate existing file only")
    ap.add_argument(
        "--dry-run", action="store_true", help="refresh + validate but do not write"
    )
    args = ap.parse_args()

    schema = load(SCHEMA)
    current = load(DATA)

    if args.check:
        validate(current, schema)
        print("existing data file is valid ✓")
        return

    print(f"refreshing with model={MODEL} ...")
    candidate = ask_claude(current, schema)

    try:
        validate(candidate, schema)
    except (jsonschema.ValidationError, ValueError) as e:
        print("REJECTED — candidate failed validation; keeping previous good file.")
        print(str(e)[:800])
        sys.exit(1)

    if candidate == current:
        print("no changes after refresh.")
        return

    if args.dry_run:
        print(
            "DRY RUN — valid candidate, not writing. Preview of `updated`:",
            candidate.get("updated"),
        )
        return

    atomic_write(DATA, candidate)
    print(f"published {DATA} (updated {candidate.get('updated')}) ✓")


if __name__ == "__main__":
    main()
