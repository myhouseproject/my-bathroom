# my-bathroom — Kreator Puzzli Łazienki

Web tool for choosing tiles for the R07 bathroom: pick a tile for each of the 5 surfaces
(floor, left / middle / right wall, ceiling) from two camera angles and see the composed render instantly.

Live: GitHub Pages, deployed from `main` by `.github/workflows/pages.yml`.

## Layout

| Path | What |
|---|---|
| `index.html` | The whole app (no build step). State lives in the URL hash, so a link = a combination. |
| `data/tiles.json` | Tile catalog (index, manufacturer, product, format). Source: `my-house/modules/06_interior/extracts/bathroom-tiles-85.yaml`. |
| `assets/<camera>/<zone>/<NN>.webp` | Puzzle layers, 2000×1600 with alpha. Generated — don't edit by hand. |
| `tools/build_assets.py` | PNG pieces → WebP layers, plus `--check` used by CI. |

## Where the images live

- **Google Drive `Dom_Lazienka_R07_Puzzle`** — master PNG pieces (≈0.4–1.5 MB each, ~700 MB total). Archive / source of truth.
- **This repo `assets/`** — WebP copies (~40× smaller, visually identical, alpha exact). These are what the site serves.

The pipeline upstream of this repo is in `my-house`: renders → `scripts/slice_all_puzzles.py` (cuts each render
into 5 pieces using the zone masks) → `Dom_Lazienka_R07_Puzzle/`.

## Updating layers

```bash
pip install -r requirements.txt
# point --src at a local copy of the puzzle folder (phone: /sdcard/Download/Dom_Lazienka_R07_Puzzle,
# PC: the Google Drive for desktop path)
python tools/build_assets.py --src /sdcard/Download/Dom_Lazienka_R07_Puzzle
python tools/build_assets.py --check
git add assets && git commit -m "Update puzzle layers" && git push
```

Only missing layers are converted; pass `--overwrite` after re-rendering.
Adding a tile: append it to `data/tiles.json`, add its pieces, run the script.

## Run locally

```bash
python -m http.server 8080   # then open http://localhost:8080
```
