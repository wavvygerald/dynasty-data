#!/usr/bin/env python3
import json, pathlib, datetime, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PMAP_DIR = ROOT / "player_maps"

FILES = {
    "WR": PMAP_DIR / "top100_wr.json",
    "RB": PMAP_DIR / "top100_rb.json",
    "QB": PMAP_DIR / "top100_qb.json",
    "TE": PMAP_DIR / "top100_te.json",
}

def load_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")

def normalize_entry(e):
    # enforce keys + types; allow seed files with partial fields
    return {
        "rank": int(e.get("rank") or 9999),
        "name": str(e.get("name") or "").strip(),
        "team": (e.get("team") or "").upper(),
        "tier": int(e.get("tier") or 9),
        "dynasty_value": int(e.get("dynasty_value") or 0),
        # carry through optional id/pos if present
        **({k: e[k] for k in ("sleeper_id","pos","number") if k in e})
    }

def process_file(pos, path):
    data = load_json(path)
    players = [normalize_entry(x) for x in data.get("players", []) if x.get("name")]
    # prefer sorting by dynasty_value desc; fallback to rank asc
    players.sort(key=lambda x: (-x.get("dynasty_value", 0), x.get("rank", 9999), x["name"]))
    # clamp to top 100 and re-rank
    players = players[:100]
    for i, p in enumerate(players, 1):
        p["rank"] = i
        p["pos"] = pos
    # update meta
    meta = dict(data.get("meta", {}))
    meta.update({
        "pos": pos,
        "version": "auto",
        "updated": datetime.date.today().isoformat(),
        "source": meta.get("source", "seed/local")
    })
    out = {"meta": meta, "players": players}
    save_json(path, out)
    print(f"✓ wrote {path.relative_to(ROOT)} ({len(players)} players)")

def main():
    missing = [p for p in FILES.values() if not p.exists()]
    if missing:
        print("Missing files:", ", ".join(str(m) for m in missing), file=sys.stderr)
        sys.exit(0)  # don’t fail CI; just skip
    for pos, path in FILES.items():
        process_file(pos, path)

if __name__ == "__main__":
    main()
