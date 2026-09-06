"""Sponsor drop-folder installer.

Workflow: drop a sponsor image into sponsors/, then either tell an agent, or run:

    python sponsors/install.py <image-file-name-in-this-folder> "Sponsor Name" [https://optional-link]
    python sponsors/install.py --list
    python sponsors/install.py --remove "Sponsor Name"

What install does:
  1. normalizes the image (RGB jpg, height capped at 240px — 2x the tile's 120px display size, never upscaled)
  2. writes it to site/sponsors/<slug>.jpg (the deployed copy)
  3. adds/updates the entry in site/data/sponsors.json (active: true)
  4. consumes the dropped original so this folder is empty again

Deeper edits (cropping to a banner, background cleanup) are agent work — ask in chat.
After installing, commit + push to deploy (same as everything else).
"""
import json, re, sys, pathlib
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
DROP = ROOT / "sponsors"
SITE_IMG = ROOT / "site" / "sponsors"
SPONSORS_JSON = ROOT / "site" / "data" / "sponsors.json"

def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "sponsor"

def load():
    return json.loads(SPONSORS_JSON.read_text(encoding="utf-8"))

def save(d):
    SPONSORS_JSON.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")

def add(fname, name, link=None):
    src = DROP / fname
    if not src.exists():
        sys.exit(f"not found in drop folder: {src}")
    img = Image.open(src).convert("RGB")
    if img.height > 240:
        img = img.resize((round(img.width * 240 / img.height), 240), Image.LANCZOS)
    SITE_IMG.mkdir(exist_ok=True)
    s = slug(name)
    dest = SITE_IMG / f"{s}.jpg"
    img.save(dest, "JPEG", quality=88, optimize=True)

    d = load()
    d["sponsors"] = [x for x in d.get("sponsors", []) if x.get("name") != name]
    entry = {"name": name, "image": f"sponsors/{s}.jpg", "active": True}
    if link:
        entry["link"] = link
    d["sponsors"].append(entry)
    save(d)

    src.unlink()  # consume the dropped original — single location wins
    print(f"installed: {name} -> {dest.relative_to(ROOT)} ({img.width}x{img.height})")
    print("deploy with:  git add site/ && git commit -m 'sponsors: add " + name + "' && git push")

def remove(name):
    d = load()
    hit = False
    for x in d.get("sponsors", []):
        if x.get("name") == name:
            x["active"] = False
            hit = True
    if not hit:
        sys.exit(f"no sponsor named {name!r}")
    save(d)
    print(f"deactivated: {name} (image kept in site/sponsors/; re-activate by setting active: true)")
    print("deploy with:  git add site/ && git commit -m 'sponsors: remove " + name + "' && git push")

if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--list"]:
        for x in load().get("sponsors", []):
            mark = "✓" if x.get("active") else "✗"
            print(f" {mark} {x['name']:<28} {x.get('image','')}  {x.get('link','')}")
    elif args[:1] == ["--remove"]:
        remove(args[1])
    elif len(args) >= 2:
        add(args[0], args[1], args[2] if len(args) > 2 else None)
    else:
        print(__doc__)
