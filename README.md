# jf-alpha

Momentum-based dashboard for a fixed top-50 US large-cap universe.

## What this repo contains
- `dashboard/`: static site (HTML/CSS/JS) for viewing buy/sell signals.
- `scripts/`: data refresh script that generates the dashboard dataset.
- `analysis_outputs/`: optional backtest outputs (ignored by default).

## How it works
The data generator pulls daily closes from Stooq, computes 12-1 momentum
(`price_t-21 / price_t-252 - 1`), then ranks the universe.
Top 20% become BUY, bottom 20% become SELL, the rest are HOLD.

## Refresh data
Set `FMP_API_KEY` in your environment (recommended via `.env`).

```
export FMP_API_KEY=your_key
```

The script caches fundamentals for 7 days to respect API limits.

You can also place the key in a `.env` file at the repo root:
```
FMP_API_KEY=your_key
```

```
. .venv/bin/activate
python scripts/update_top50_dashboard.py
```

This writes:
- `dashboard/data/top50_signals.json`
- `dashboard/data/top50_signals.js`

## View the dashboard
Open `dashboard/index.html` in a browser.

## Publish to GitHub Pages
This project uses a `gh-pages` worktree to publish static files.

```
cp -R dashboard/* .gh-pages/
cd .gh-pages
git add .
git commit -m "Update dashboard data"
git push origin gh-pages
```

Then enable GitHub Pages in repo settings using `gh-pages` as the source.

## GitHub Actions secret
Add `FMP_API_KEY` in repo settings:
Settings → Secrets and variables → Actions → New repository secret.
