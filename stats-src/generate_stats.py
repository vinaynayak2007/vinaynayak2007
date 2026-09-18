#!/usr/bin/env python3
"""
Generate GitHub stats cards as self-contained SVG files.

Why this exists: the public github-readme-stats / streak-stats services are
rate-limited and go down constantly (HTTP 503), leaving broken images on the
profile. This script builds the cards from the GitHub API directly and commits
them as files, so the README has zero external dependencies and nothing to break.

Icons are drawn as vector paths, not emoji — emoji render as empty boxes
wherever the font is missing, which is unreliable across clients.

Usage:
    GITHUB_TOKEN=xxx python generate_stats.py

Env:
    GITHUB_TOKEN       required; needs repo + read:user for private counts
    GH_USER            optional, defaults to vinaynayak2007
    OUT_DIR            optional, defaults to 'assets'
    INCLUDE_PRIVATE    '1' to fold private-repo languages into the totals
"""

import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

USER = os.environ.get("GH_USER", "vinaynayak2007")
OUT_DIR = os.environ.get("OUT_DIR", "assets")
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
INCLUDE_PRIVATE = os.environ.get("INCLUDE_PRIVATE", "1") == "1"

API = "https://api.github.com"

# ── theme (matches the profile banner) ────────────────────────────────────────
BG = "#0D1117"
BORDER = "#30363D"
TITLE = "#0EA5E9"
TEXT = "#C9D1D9"
MUTED = "#8B949E"
DIM = "#6E7681"
ACCENT = "#0EA5E9"
GREEN = "#3FB950"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#F1E05A", "TypeScript": "#3178C6",
    "HTML": "#E34C26", "CSS": "#563D7C", "PHP": "#4F5D95", "Java": "#B07219",
    "C": "#555555", "C++": "#F34B7D", "C#": "#178600", "Shell": "#89E051",
    "Dart": "#00B4AB", "Kotlin": "#A97BFF", "Go": "#00ADD8", "Rust": "#DEA584",
    "Ruby": "#701516", "Swift": "#F05138", "Vue": "#41B883", "SCSS": "#C6538C",
    "PowerShell": "#012456", "Batchfile": "#C1F12E",
}
DEFAULT_LANG_COLOR = "#8B949E"

# GitHub language detection tags these; they are build artefacts, not languages
NON_LANGUAGES = {
    "Dockerfile", "Procfile", "Makefile", "Batchfile", "Text", "Shell",
    ".gitignore", "EditorConfig", "Git Attributes", "INI", "YAML", "TOML",
    "JSON", "Markdown", "CMake", "Roff", "Groovy",
}


# ── api helpers ───────────────────────────────────────────────────────────────

def _req(url, data=None, method="GET"):
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", f"{USER}-stats-generator")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        print(f"  ! HTTP {e.code} {url} :: "
              f"{e.read().decode(errors='replace')[:200]}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ! {type(e).__name__} {url} :: {e}", file=sys.stderr)
        return None


def get_rest(path):
    return _req(API + path) or {}


def graphql(query, variables):
    payload = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(API + "/graphql", data=payload, method="POST")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", f"{USER}-stats-generator")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req) as r:
            d = json.loads(r.read())
        if "errors" in d:
            print(f"  ! GraphQL: {d['errors'][0].get('message')}", file=sys.stderr)
        return d.get("data") or {}
    except Exception as e:
        print(f"  ! GraphQL failed: {e}", file=sys.stderr)
        return {}


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ── vector icons (no emoji — emoji render as tofu boxes) ──────────────────────

def icon(kind, x, y, color=MUTED, size=14):
    """Return an <g> with a small geometric glyph drawn at (x, y) top-left."""
    p = {'star': f'<polygon points="7,0.6 8.9,5.0 13.6,5.4 10.0,8.3 11.2,12.8 '
                  f'7,10.3 2.8,12.8 4.0,8.3 0.4,5.4 5.1,5.0"/>',
         'repo': f'<rect x="0.7" y="0.7" width="12.6" height="12.6" rx="2" '
                 f'fill="none" stroke="{color}" stroke-width="1.5"/>'
                 f'<line x1="4.4" y1="0.7" x2="4.4" y2="13.3" '
                 f'stroke="{color}" stroke-width="1.5"/>',
         'users': f'<circle cx="5.2" cy="4.6" r="2.7" fill="{color}"/>'
                  f'<path d="M0.6 13.4c0-2.6 2.1-4.4 4.6-4.4s4.6 1.8 4.6 4.4z" '
                  f'fill="{color}"/>'
                  f'<circle cx="11.2" cy="5.4" r="2" fill="{color}" '
                  f'opacity="0.55"/>'
                  f'<path d="M9.4 13.4c0-2 0.8-3.5 2.2-4a3.9 3.9 0 0 1 1.8 4z" '
                  f'fill="{color}" opacity="0.55"/>',
         'commit': f'<circle cx="7" cy="7" r="3.1" fill="none" stroke="{color}" '
                   f'stroke-width="1.5"/>'
                   f'<line x1="0.5" y1="7" x2="3.4" y2="7" stroke="{color}" '
                   f'stroke-width="1.5"/>'
                   f'<line x1="10.6" y1="7" x2="13.5" y2="7" stroke="{color}" '
                   f'stroke-width="1.5"/>',
         'pr': f'<circle cx="4" cy="3.2" r="2.2" fill="none" stroke="{color}" '
               f'stroke-width="1.5"/>'
               f'<circle cx="4" cy="11" r="2.2" fill="none" stroke="{color}" '
               f'stroke-width="1.5"/>'
               f'<circle cx="10.6" cy="11" r="2.2" fill="none" stroke="{color}" '
               f'stroke-width="1.5"/>'
               f'<path d="M4 5.4v3.4" stroke="{color}" stroke-width="1.5"/>'
               f'<path d="M10.6 8.8V6.2c0-1.4-1.1-2.4-2.5-2.4H6.6" '
               f'fill="none" stroke="{color}" stroke-width="1.5"/>',
         'bug': f'<circle cx="7" cy="7.4" r="4.2" fill="none" stroke="{color}" '
                f'stroke-width="1.5"/>'
                f'<circle cx="7" cy="7.4" r="1.5" fill="{color}"/>'
                f'<path d="M2.6 3.2 5 5.2M11.4 3.2 9 5.2M2.2 11.8 4.6 10.4'
                f'M11.8 11.8 9.4 10.4" stroke="{color}" stroke-width="1.4"/>',
         'eye': f'<path d="M0.7 7S3.3 2.6 7 2.6 13.3 7 13.3 7 10.7 11.4 7 11.4 '
                f'0.7 7 0.7 7z" fill="none" stroke="{color}" '
                f'stroke-width="1.5"/>'
                f'<circle cx="7" cy="7" r="1.9" fill="{color}"/>',
         }
    return (f'<g transform="translate({x},{y-10}) scale({size/14:.3f})" '
            f'opacity="0.95">{p.get(kind, "")}</g>')


# ── data collection ───────────────────────────────────────────────────────────

def fetch_profile():
    u = get_rest(f"/users/{USER}")
    return {
        "name": (u.get("name") or USER).strip(),
        "public_repos": u.get("public_repos", 0),
        "followers": u.get("followers", 0),
        "following": u.get("following", 0),
    }


def fetch_repos():
    """All owner repos. Returns (public_list, private_count)."""
    repos, page = [], 1
    while page <= 3:
        chunk = _req(f"{API}/user/repos?per_page=100&page={page}"
                     f"&affiliation=owner&visibility=all")
        if not chunk or not isinstance(chunk, list):
            break
        repos.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
    public = [r for r in repos if not r["private"] and not r.get("fork")]
    private = [r for r in repos if r["private"] and not r.get("fork")]
    return public, private


def fetch_languages(repos, include_private):
    totals = Counter()
    for r in repos:
        langs = get_rest(f"/repos/{USER}/{r['name']}/languages")
        if isinstance(langs, dict):
            for k, v in langs.items():
                if k not in NON_LANGUAGES:
                    totals[k] += v
    return totals


def fetch_contributions():
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=365)
    q = """
    query($login:String!, $from:DateTime!, $to:DateTime!) {
      user(login:$login) {
        contributionsCollection(from:$from, to:$to) {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          totalPullRequestReviewContributions
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }"""
    d = graphql(q, {"login": USER,
                    "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "to": now.strftime("%Y-%m-%dT%H:%M:%SZ")})
    cc = ((d.get("user") or {}).get("contributionsCollection") or {})
    cal = cc.get("contributionCalendar") or {}

    days = []
    for w in cal.get("weeks", []):
        for day in w.get("contributionDays", []):
            days.append((day["date"], day["contributionCount"]))
    days.sort(key=lambda x: x[0])

    today = now.date()
    current = 0
    if days:
        try:
            last_date = datetime.strptime(days[-1][0], "%Y-%m-%d").date()
        except ValueError:
            last_date = today
        if (today - last_date).days <= 1:
            for _, c in reversed(days):
                if c > 0:
                    current += 1
                else:
                    break

    longest = run = 0
    for _, c in days:
        if c > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    return {
        "total": cal.get("totalContributions", 0),
        "current": current,
        "longest": longest,
        "commits": cc.get("totalCommitContributions", 0),
        "prs": cc.get("totalPullRequestContributions", 0),
        "issues": cc.get("totalIssueContributions", 0),
        "reviews": cc.get("totalPullRequestReviewContributions", 0),
    }


# ── svg builders ──────────────────────────────────────────────────────────────

def _card_open(w, h, title, subtitle=None):
    parts = [
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{esc(title)}">',
        '<style>'
        f'text{{font-family:{FONT}}}'
        f'.h{{fill:{TITLE};font-weight:600}}'
        f'.m{{fill:{MUTED};font-size:12px}}'
        f'.d{{fill:{DIM};font-size:11px}}'
        f'.b{{fill:{TEXT};font-size:13.5px}}'
        f'.v{{fill:{TEXT};font-size:13.5px;font-weight:700}}'
        '</style>',
        f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" '
        f'fill="{BG}" stroke="{BORDER}"/>',
        f'<text x="25" y="30" class="h" font-size="17">{esc(title)}</text>',
    ]
    if subtitle:
        parts.append(f'<text x="25" y="48" class="d">{esc(subtitle)}</text>')
    return parts


def svg_stats(p, c, private_count, stars, subtitle):
    w, h = 495, 218
    s = _card_open(w, h, f"{p['name']}'s GitHub Stats", subtitle)
    rows = [
        ("star", "Total Stars Earned", f"{stars:,}"),
        ("repo", "Public Repositories", f"{p['public_repos']:,}"),
        ("repo", "Private Repositories", f"{private_count:,}"),
        ("users", "Followers", f"{p['followers']:,}"),
        ("commit", "Commits (12 mo)", f"{c.get('commits', 0):,}"),
        ("pr", "Pull Requests (12 mo)", f"{c.get('prs', 0):,}"),
        ("bug", "Issues Opened (12 mo)", f"{c.get('issues', 0):,}"),
        ("eye", "Code Reviews (12 mo)", f"{c.get('reviews', 0):,}"),
    ]
    y = 76
    for kind, label, value in rows:
        s.append(icon(kind, 25, y))
        s.append(f'<text x="52" y="{y}" class="b">{esc(label)}</text>')
        s.append(f'<text x="248" y="{y}" class="v" text-anchor="end">'
                 f'{esc(value)}</text>')
        y += 18
    s.append('</svg>')
    return "\n".join(s)


def svg_langs(totals, subtitle, top_n=5):
    w, h = 495, 218
    s = _card_open(w, h, "Most Used Languages", subtitle)
    total = sum(totals.values()) or 1
    top = totals.most_common(top_n)

    if not top:
        s.append(f'<text x="25" y="90" class="m">'
                 f'No language data yet — push some code.</text>')
    y = 78
    for lang, bytes_ in top:
        pct = bytes_ / total * 100
        color = LANG_COLORS.get(lang, DEFAULT_LANG_COLOR)
        bar_w = max(3, int(430 * pct / 100))
        s.append(f'<text x="25" y="{y}" class="b">{esc(lang)}</text>')
        s.append(f'<text x="455" y="{y}" class="m" text-anchor="end">'
                 f'{pct:.1f}%</text>')
        s.append(f'<rect x="25" y="{y+7}" width="430" height="7" rx="3.5" '
                 f'fill="{BORDER}"/>')
        s.append(f'<rect x="25" y="{y+7}" width="{bar_w}" height="7" rx="3.5" '
                 f'fill="{color}"/>')
        y += 26
    s.append('</svg>')
    return "\n".join(s)


def svg_streak(c, subtitle):
    w, h = 495, 218
    s = _card_open(w, h, "Contribution Streak", subtitle)
    centres = (82, 247, 412)
    cols = [
        (centres[0], "Current Streak", c["current"], "days", GREEN),
        (centres[1], "Past Year", c["total"], "contributions", ACCENT),
        (centres[2], "Longest Streak", c["longest"], "days", GREEN),
    ]
    s.append(f'<line x1="165" y1="78" x2="165" y2="190" stroke="{BORDER}"/>')
    s.append(f'<line x1="330" y1="78" x2="330" y2="190" stroke="{BORDER}"/>')
    for x, label, value, unit, color in cols:
        s.append(f'<text x="{x}" y="106" class="m" text-anchor="middle" '
                 f'font-size="11.5">{esc(label)}</text>')
        s.append(f'<text x="{x}" y="148" font-size="36" font-weight="700" '
                 f'text-anchor="middle" fill="{color}">{value:,}</text>')
        s.append(f'<text x="{x}" y="170" class="d" text-anchor="middle">'
                 f'{esc(unit)}</text>')
    s.append('</svg>')
    return "\n".join(s)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    if not TOKEN:
        print("! GITHUB_TOKEN unset — unauthenticated calls will be rate limited",
              file=sys.stderr)

    print(f"→ collecting for {USER}")
    profile = fetch_profile()
    public, private = fetch_repos()
    stars = sum(r.get("stargazers_count", 0) for r in public)
    print(f"  {len(public)} public, {len(private)} private, {stars} stars")

    print("→ languages")
    pool = public + (private if INCLUDE_PRIVATE else [])
    langs = fetch_languages(pool, INCLUDE_PRIVATE)
    print(f"  {len(langs)} languages: {', '.join(l for l, _ in langs.most_common(6))}")

    print("→ contributions")
    contrib = fetch_contributions()
    print(f"  {contrib['total']} contributions · streak {contrib['current']}")

    stamp = datetime.now(timezone.utc).strftime("%d %b %Y")
    files = {
        "stats.svg": svg_stats(profile, contrib, len(private), stars,
                               f"Updated {stamp} · public & private activity"),
        "langs.svg": svg_langs(langs,
                               f"Updated {stamp} · by bytes of code"),
        "streak.svg": svg_streak(contrib, f"Updated {stamp} · last 12 months"),
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    for name, content in files.items():
        path = os.path.join(OUT_DIR, name)
        with open(path, "w") as f:
            f.write(content)
        print(f"  ✓ {path} ({len(content):,} bytes)")
    print("done.")


if __name__ == "__main__":
    main()
