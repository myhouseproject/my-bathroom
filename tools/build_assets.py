#!/usr/bin/env python3
"""Convert puzzle pieces (PNG) into the compressed WebP layers served by the web app.

Source layout (e.g. a local copy of Drive 'Dom_Lazienka_R07_Puzzle', or the output
of my-house/scripts/slice_all_puzzles.py):

    <src>/<camera>/<zone>/<NN>_<anything>.png       camera: entrance|reverse

Output layout (committed to the repo, served by GitHub Pages):

    assets/<camera>/<zone>/<NN>.webp

Usage:
    python tools/build_assets.py --src /sdcard/Download/Dom_Lazienka_R07_Puzzle
    python tools/build_assets.py --check            # only verify assets vs data/tiles.json
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'data/tiles.json'
ASSETS = ROOT / 'assets'
CAMERAS = ['entrance', 'reverse']
ZONES = ['podloga', 'sciana_lewa', 'sciana_srodkowa', 'sciana_prawa', 'sufit']


def load_indices():
    with open(CATALOG, encoding='utf-8') as f:
        return [t['index'] for t in json.load(f)['tiles']]


def asset_path(camera, zone, idx):
    return ASSETS / camera / zone / f'{idx:02d}.webp'


def find_source(src, camera, zone, idx):
    zone_dir = src / camera / zone
    if not zone_dir.is_dir():
        return None
    prefix = f'{idx:02d}_'
    matches = sorted(p for p in zone_dir.iterdir() if p.name.startswith(prefix) and p.suffix.lower() == '.png')
    return matches[0] if matches else None


def require_pillow_webp():
    try:
        from PIL import features
    except ImportError:
        sys.exit('Pillow is not installed. Termux: pkg install python-pillow   PC: pip install Pillow')
    if not features.check('webp'):
        sys.exit('This Pillow build has no WebP support. Termux: pkg install libwebp && pkg reinstall python-pillow')


def convert(task):
    src_path, dst_path, quality = task
    try:
        return _convert(src_path, dst_path, quality)
    except Exception as exc:  # report and keep going; one bad file must not stop 840
        return src_path, f'{type(exc).__name__}: {exc}'


def _convert(src_path, dst_path, quality):
    from PIL import Image
    with Image.open(src_path) as img:
        img = img.convert('RGBA')
        if img.size != (2000, 1600):
            return src_path, f'unexpected size {img.size}'
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst_path.with_suffix('.tmp.webp')
        # exact=False lets libwebp drop RGB data under fully transparent pixels,
        # which is most of every piece -> files shrink ~40x versus PNG.
        img.save(tmp, 'WEBP', quality=quality, method=4, exact=False)
        os.replace(tmp, dst_path)
    return src_path, None


def check(indices):
    missing = [asset_path(c, z, i) for c in CAMERAS for z in ZONES for i in indices
               if not asset_path(c, z, i).exists()]
    expected = {asset_path(c, z, i) for c in CAMERAS for z in ZONES for i in indices}
    orphans = sorted(p for p in ASSETS.rglob('*.webp') if p not in expected) if ASSETS.exists() else []
    total = len(CAMERAS) * len(ZONES) * len(indices)
    print(f'{total - len(missing)}/{total} layers present, {len(orphans)} orphan files')
    for cam in CAMERAS:
        for zone in ZONES:
            n = sum(1 for p in missing if p.parent == ASSETS / cam / zone)
            if n:
                print(f'  missing {n:3d} in {cam}/{zone}')
    for p in orphans:
        print(f'  orphan: {p.relative_to(ROOT)}')
    return missing, orphans


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--src', type=Path, help='Folder with <camera>/<zone>/*.png puzzle pieces')
    parser.add_argument('--quality', type=int, default=82, help='WebP quality (default 82)')
    parser.add_argument('--overwrite', action='store_true', help='Re-encode layers that already exist')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--check', action='store_true', help='Only verify assets against the catalog')
    parser.add_argument('--strict', action='store_true', help='With --check: exit 1 when layers are missing')
    args = parser.parse_args()

    indices = load_indices()

    if args.check:
        missing, orphans = check(indices)
        if os.environ.get('GITHUB_ACTIONS') and missing:
            print(f'::warning::{len(missing)} tile layers are missing; the app will show them as gaps')
        sys.exit(1 if orphans or (args.strict and missing) else 0)

    if not args.src:
        parser.error('--src is required (folder that contains entrance/ and reverse/)')
    if not args.src.is_dir():
        sys.exit(f'--src folder does not exist or is not readable: {args.src}\n'
                 'Termux: run termux-setup-storage once and allow file access.')
    cams_found = [c for c in CAMERAS if (args.src / c).is_dir()]
    if not cams_found:
        listing = sorted(p.name for p in args.src.iterdir())[:20]
        sys.exit(f'No entrance/ or reverse/ folder inside {args.src}\nIt contains: {listing}\n'
                 'Point --src at the folder that directly contains entrance/ and reverse/.')
    require_pillow_webp()

    tasks, not_found = [], []
    for cam in CAMERAS:
        for zone in ZONES:
            for idx in indices:
                dst = asset_path(cam, zone, idx)
                if dst.exists() and not args.overwrite:
                    continue
                src = find_source(args.src, cam, zone, idx)
                if src is None:
                    not_found.append(f'{cam}/{zone}/{idx:02d}')
                else:
                    tasks.append((src, dst, args.quality))

    print(f'Converting {len(tasks)} pieces with {args.workers} threads...')
    errors = []
    # Threads, not processes: Pillow releases the GIL while encoding, and
    # multiprocessing is broken on Android/Termux (no sem_open).
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n, (src, err) in enumerate(pool.map(convert, tasks), 1):
            if err:
                errors.append(f'{src}: {err}')
            if n % 10 == 0 or n == len(tasks):
                print(f'  [{n}/{len(tasks)}]')

    if not_found:
        print(f'No source PNG for {len(not_found)} layers (first: {", ".join(not_found[:5])})')
    for e in errors[:20]:
        print(f'ERROR {e}')
    if len(errors) > 20:
        print(f'... and {len(errors) - 20} more errors')
    check(indices)
    size = sum(p.stat().st_size for p in ASSETS.rglob('*.webp'))
    print(f'assets/ total: {size / 1e6:.1f} MB')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
