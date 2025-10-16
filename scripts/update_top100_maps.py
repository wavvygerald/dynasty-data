import os, io, json, csv, time, math, unicodedata, requests
from collections import defaultdict

REPO_RAW = "https://raw.githubusercontent.com/wavvygerald/dynasty-data/main"
VALUES_PATH = f"{REPO_RAW}/dynasty_trade_values.csv"   # or keep local in repo
OUTPUT_DIR = "data/player_maps"
PPR_MULT = {"WR":1.06, "TE":1.03, "RB":0.96, "QB":1.00}

def slug(s):  # simple name normalizer
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.replace("-", " ").split()).strip().lower()

def fetch_csv(url_or_path):
    if url_or_path.startswith("http"):
        r = requests.get(url_or_path, timeout=30)
        r.raise_for_status()
        text = r.text
    else:
        with open(url_or_path, "r", encoding="utf-8") as f:
            text = f.read()
    return list(csv.DictReader(io.StringIO(text)))

def fetch_sleeper_players():
    url = "https://api.sleeper.app/v1/players/nfl"
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return r.json()  # dict keyed by player_id

def build_lookup(players_json):
    by_key = {}  # (slug(name), pos)-> info
    for pid, p in players_json.items():
        pos = p.get("position")
        if not pos: continue
        first = p.get("first_name","") or ""
        last  = p.get("last_name","") or ""
        full  = p.get("full_name") or f"{first} {last}".strip()
        if not full: continue
        key = (slug(full), pos.upper())
        by_key[key] = {
            "sleeper_id": pid,
            "name": full,
            "pos": pos.upper(),
            "team": p.get("team"),
            "number": p.get("number")
        }
    return by_key

def adjust_value(row):
    pos = (row.get("Position") or "").upper()
    try:
        base = float(row.get("DynastyValueScore") or row.get("Value") or 0)
    except:
        base = 0.0
    mult = PPR_MULT.get(pos, 1.0)
    return base * mult

def top100_by_pos(rows):
    buckets = defaultdict(list)
    for r in rows:
        pos = (r.get("Position") or "").upper()
        if pos not in {"QB","RB","WR","TE"}: continue
        r["_adj"] = adjust_value(r)
        buckets[pos].append(r)
    out = {}
    for pos, arr in buckets.items():
        arr.sort(key=lambda x: x["_adj"], reverse=True)
        out[pos] = arr[:100]
    return out

def make_payload(list_rows, lookup, pos):
    players = []
    for r in list_rows:
        name = (r.get("Player") or r.get("Player Name") or "").strip()
        team = (r.get("Team") or "").strip() or None
        key  = (slug(name), pos)
        info = lookup.get(key)
        players.append({
            "sleeper_id": info["sleeper_id"] if info else None,
            "name": info["name"] if info else name,
            "pos": pos,
            "team": info["team"] if info and info.get("team") else team,
            "number": info.get("number") if info else None
        })
    return {
        "meta": {"pos": pos, "version": "v1", "source": "CJ dynasty values + Sleeper"},
        "players": players
    }

def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

def main():
    values = fetch_csv(VALUES_PATH)
    sleeper = fetch_sleeper_players()
    lookup = build_lookup(sleeper)
    buckets = top100_by_pos(values)

    maps = {
        "QB": "data/player_maps/top100_qb.json",
        "RB": "data/player_maps/top100_rb.json",
        "WR": "data/player_maps/top100_wr.json",
        "TE": "data/player_maps/top100_te.json"
    }
    for pos, outpath in maps.items():
        payload = make_payload(buckets.get(pos, []), lookup, pos)
        write_json(outpath, payload)
        print(f"Wrote {outpath} ({len(payload['players'])} entries)")

if __name__ == "__main__":
    main()
