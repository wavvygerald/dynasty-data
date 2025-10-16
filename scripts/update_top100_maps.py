#!/usr/bin/env python3
import json, time, datetime, pathlib, re, sys, random
import requests
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "player_maps"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "DynastyDataBot/1.0 (+https://github.com/wavvygerald/dynasty-data)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

POSITIONS = ["QB", "RB", "WR", "TE"]
FORMAT = 1  # 1QB (change to 0 for SF if you ever want)
BASE = "https://keeptradecut.com/dynasty-rankings?page={page}&filters={pos}&format={fmt}"

def fetch(page: int, pos: str) -> str:
    url = BASE.format(page=page, pos=pos, fmt=FORMAT)
    r = requests.get(url, headers=HEADERS, timeout=25)
    # Surface rate-limit or blocking clearly
    if r.status_code in (403, 429):
        raise RuntimeError(f"KTC blocked/ratelimited (HTTP {r.status_code}) for {pos} p{page}")
    r.raise_for_status()
    return r.text

def parse_players(html: str, pos: str):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".onePlayer")
    out = []
    for card in cards:
        name_el = card.select_one(".player-name")
        pos_el  = card.select_one(".position")
        val_el  = card.select_one(".value")
        tier_el = card.select_one(".tier")

        name_txt = (name_el.get_text(strip=True) if name_el else "").strip()
        if not name_txt:
            continue

        # strip trailing team suffix like ATL, LAR, FA, RFA
        team = ""
        m = re.search(r"\s([A-Z]{2,3})$", name_txt)
        if m and m.group(1) not in {"FA","RFA"}:
            team = m.group(1)
            name_txt = name_txt[:m.start()].strip()

        try:
            value = int((val_el.get_text(strip=True) if val_el else "0").replace(",", ""))
        except:
            value = 0

        tier_text = tier_el.get_text(strip=True) if tier_el else ""
        tmatch = re.search(r"(\d+)", tier_text)
        tier = int(tmatch.group(1)) if tmatch else 0

        out.append({
            "name": name_txt,
            "team": team,
            "dynasty_value": value,
            "tier": tier,
            "pos": pos
        })
    return out

def pull_top100(pos: str):
    all_rows = []
    # KTC shows ~50 per page; grab until a page returns 0 (max 10 pages)
    for page in range(1, 11):
        html = fetch(page, pos)
        rows = parse_players(html, pos)
        if not rows:
            break
        all_rows.extend(rows)
        time.sleep(0.8 + random.random()*0.4)  # polite jitter

    # de-dupe by name+team, keep the highest value
    merged = {}
    for p in all_rows:
        key = (p["name"], p.get("team",""))
        if key not in merged or p["dynasty_value"] > merged[key]["dynasty_value"]:
            merged[key] = p

    players = list(merged.values())
    players.sort(key=lambda x: (-x.get("dynasty_value", 0), x["name"]))
    players = players[:100]
    for i, p in enumerate(players, 1):
        p["rank"] = i
    return players

def write_out(pos: str, players):
    meta = {
        "pos": pos,
        "version": "ktc-auto",
        "source": "KeepTradeCut (scraped dynasty PPR)",
        "updated": datetime.date.today().isoformat()
    }
    out = {"meta": meta, "players": players}
    path = OUT_DIR / f"top100_{pos.lower()}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"✓ wrote {path.relative_to(ROOT)} ({len(players)} players)")

def main():
    errors = []
    for pos in POSITIONS:
        try:
            players = pull_top100(pos)
            print(f"{pos}: scraped {len(players)} players")
            # Fail hard if clearly wrong
            if len(players) < 50:
                raise RuntimeError(f"too few players for {pos}: {len(players)}")
            write_out(pos, players)
        except Exception as e:
            print(f"!! {pos} failed: {e}")
            errors.append((pos, str(e)))

    if errors:
        print("Errors:", errors)
        sys.exit(1)  # make the workflow FAIL so we notice it

if __name__ == "__main__":
    main()
