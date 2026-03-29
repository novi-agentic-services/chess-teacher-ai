import re
import requests

TWIC_LIST_URL = "https://theweekinchess.com/twic"


def discover_twic_sources(limit: int = 50):
    """Best-effort parser of TWIC PGN zip links from TWIC page."""
    res = requests.get(TWIC_LIST_URL, timeout=20)
    res.raise_for_status()
    html = res.text

    # Example patterns often include twic1234g.zip
    matches = re.findall(r'(https?://[^"\']*twic(\d+)g\.zip)', html, re.IGNORECASE)
    seen = set()
    out = []
    for url, issue in matches:
        issue_num = int(issue)
        if issue_num in seen:
            continue
        seen.add(issue_num)
        out.append({"issue": issue_num, "url": url})
    out.sort(key=lambda x: x["issue"], reverse=True)
    return out[:limit]
