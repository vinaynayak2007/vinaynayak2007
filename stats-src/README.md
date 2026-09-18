# 📊 Stats card generator

Generates the three stat cards on my profile — `stats.svg`, `langs.svg`, `streak.svg` — as **self-contained local SVG files**.

## Why not use github-readme-stats?

Because it breaks. Public badge services like `github-readme-stats` and `streak-stats` are free, unauthenticated and hammered by thousands of profiles, so they hit GitHub's API rate limits and return **`503`**. When that happens your profile shows a broken image icon or a sad face.

I hit exactly that. This script removes the dependency entirely — the cards are generated once, committed as files, and served from the repo. Nothing external to rate-limit, nothing to go down.

**Trade-off:** the cards are a snapshot, not live. That's what the workflow is for.

## Files

| File | Purpose |
| :--- | :--- |
| `generate_stats.py` | The generator |
| `update-stats.yml` | GitHub Actions workflow (daily refresh) |
| `../assets/*.svg` | The generated cards, committed |

## Run it locally

```bash
GITHUB_TOKEN=ghp_xxx \
GH_USER=vinaynayak2007 \
OUT_DIR=../assets \
INCLUDE_PRIVATE=1 \
python generate_stats.py
```

| Env var | Required | Notes |
| :--- | :--- | :--- |
| `GITHUB_TOKEN` | recommended | Without it you're rate-limited to 60 requests/hour and private data is invisible |
| `GH_USER` | no | Defaults to `vinaynayak2007` |
| `OUT_DIR` | no | Defaults to `assets` |
| `INCLUDE_PRIVATE` | no | `1` folds private-repo languages into the totals |

## How the workflow works

`update-stats.yml` regenerates the cards **daily at 03:00 UTC** and commits any changes. To install it:

```bash
mkdir -p .github/workflows
cp stats-src/update-stats.yml .github/workflows/
git add .github/workflows && git commit -m "ci: auto-refresh stats cards" && git push
```

### Optional: see private activity in the cards

The workflow uses `secrets.STATS_TOKEN` if it exists, and falls back to the default `GITHUB_TOKEN` otherwise. The default token **cannot see your private repos**, so private languages and private contribution counts will read as zero.

To include them, create a fine-grained token and add it:

1. Go to **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**
2. **Repository access:** select only what's needed
3. **Permissions:** `Metadata: Read` (required), plus `Contents: Read`
4. **Expiration:** 90 days
5. Copy it, then add it as a repo secret named **`STATS_TOKEN`** at
   `https://github.com/vinaynayak2007/vinaynayak2007/settings/secrets/actions`

> 🔐 Never commit a token to this repo. Only ever put it in Actions secrets.

## Design notes

- **No emoji in the SVGs.** Emoji render as empty boxes wherever the font is missing — which is most Linux renderers and plenty of browsers. All icons are drawn vector paths instead, so they look identical everywhere.
- **Theme matches the profile banner** — `#0D1117` background, `#0EA5E9` accent, `#3FB950` for streaks.
- **Build artefacts are filtered out** of the language totals. GitHub counts `Dockerfile`, `Procfile` and similar as "languages", which is noise.
- Cards are `495 × 218` so they sit two-up on wide screens and stack on mobile.

## Requirements

Python 3.8+. Standard library only — no `pip install` needed.
