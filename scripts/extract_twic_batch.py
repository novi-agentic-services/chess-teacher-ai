#!/usr/bin/env python3
import json
import re
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ZIP_DIR = BASE / "data" / "twic"
PGN_DIR = BASE / "data" / "pgn"
REPORT = BASE / "data" / "twic_extraction_report.json"

PGN_DIR.mkdir(parents=True, exist_ok=True)

event_re = re.compile(r"^\[Event ", re.MULTILINE)

zips = sorted(ZIP_DIR.glob("twic*g.zip"), key=lambda p: int(re.sub(r"\D", "", p.stem)))

results = []
total_games = 0

for z in zips:
    issue = int(re.sub(r"\D", "", z.stem))
    try:
        with zipfile.ZipFile(z, "r") as zf:
            members = [m for m in zf.namelist() if m.lower().endswith(".pgn")]
            if not members:
                results.append({"issue": issue, "zip": z.name, "status": "no_pgn"})
                continue
            member = members[0]
            out_path = PGN_DIR / Path(member).name
            if not out_path.exists():
                out_path.write_bytes(zf.read(member))
            txt = out_path.read_text(errors="ignore")
            games = len(event_re.findall(txt))
            total_games += games
            results.append(
                {
                    "issue": issue,
                    "zip": z.name,
                    "pgn": out_path.name,
                    "size_bytes": out_path.stat().st_size,
                    "games": games,
                    "status": "ok",
                }
            )
    except zipfile.BadZipFile:
        results.append({"issue": issue, "zip": z.name, "status": "bad_zip"})

report = {
    "zip_count": len(zips),
    "pgn_count": len(list(PGN_DIR.glob("*.pgn"))),
    "total_games_estimate": total_games,
    "issues_min": min((r["issue"] for r in results if r.get("status") == "ok"), default=None),
    "issues_max": max((r["issue"] for r in results if r.get("status") == "ok"), default=None),
    "items": results,
}

REPORT.write_text(json.dumps(report, indent=2))
print(json.dumps({
    "zip_count": report["zip_count"],
    "pgn_count": report["pgn_count"],
    "total_games_estimate": report["total_games_estimate"],
    "issues_min": report["issues_min"],
    "issues_max": report["issues_max"],
}, indent=2))
