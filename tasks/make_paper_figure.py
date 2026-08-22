"""
Qualitative comparison figure for the paper.

Selects test images by how much the two arms differ in *color* error, so the
figure shows the phenomenon under discussion rather than a hand-picked
flattering example. The per-image color error is printed under each column so a
reader can check the claim against the numbers, and the selection rule is stated
in the caption rather than left implicit.

Usage:
    python tasks/make_paper_figure.py --n 5 --out paper/qualitative.png
"""
import argparse
import glob
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


def color_err(a, b):
    """Mean absolute difference of per-channel means, in 0-255 units."""
    return float(np.abs(a.reshape(-1, 3).mean(0) - b.reshape(-1, 3).mean(0)).mean())


def latest(exp):
    d = sorted(glob.glob(f'checkpoints/{exp}/results_*'))
    assert d, f'no results for {exp}'
    return d[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', default='diffsr_celebA_small_baseline')
    ap.add_argument('--cc', default='diffsr_celebA_small_cc')
    ap.add_argument('--n', type=int, default=5)
    ap.add_argument('--out', default='paper/qualitative.png')
    ap.add_argument('--mode', default='best', choices=['best', 'worst', 'random'],
                    help="best = largest CC advantage; worst = largest CC "
                         "disadvantage (include one for an honest figure)")
    ap.add_argument('--min_std', type=float, default=0.0,
                    help='skip ground-truth tiles flatter than this pixel std. '
                         'A content criterion, evaluated on the ground truth only, '
                         'so it cannot favour either arm; use it to avoid filling '
                         'a figure with empty sky.')
    args = ap.parse_args()

    bd, cd = latest(args.baseline), latest(args.cc)
    names = [os.path.basename(p) for p in sorted(glob.glob(f'{bd}/SR/*.png'))]
    assert names, 'no SR images found; run tasks/evaluate.py first'

    rows = []
    for n in names:
        hr = np.array(Image.open(f'{bd}/HR/{n}').convert('RGB')).astype(np.float64)
        sb = np.array(Image.open(f'{bd}/SR/{n}').convert('RGB')).astype(np.float64)
        cp = f'{cd}/SR/{n}'
        if not os.path.exists(cp):
            continue
        sc = np.array(Image.open(cp).convert('RGB')).astype(np.float64)
        if args.min_std and hr.std() < args.min_std:
            continue
        eb, ec = color_err(sb, hr), color_err(sc, hr)
        rows.append((n, eb, ec, eb - ec))

    if args.mode == 'best':
        rows.sort(key=lambda r: -r[3])
    elif args.mode == 'worst':
        rows.sort(key=lambda r: r[3])
    else:
        rng = np.random.RandomState(0)
        rng.shuffle(rows)
    sel = rows[:args.n]

    cols = [('LR input', bd, 'LR'), ('Bicubic', bd, 'UP'),
            ('Baseline', bd, 'SR'), ('CC-ResDiff', cd, 'SR'), ('Ground truth', bd, 'HR')]
    fig, axes = plt.subplots(len(sel), len(cols),
                             figsize=(2.05 * len(cols), 2.25 * len(sel)))
    axes = np.atleast_2d(axes)
    for i, (n, eb, ec, _) in enumerate(sel):
        for j, (label, d, sub) in enumerate(cols):
            ax = axes[i, j]
            ax.imshow(Image.open(f'{d}/{sub}/{n}').convert('RGB'))
            ax.set_xticks([]); ax.set_yticks([])
            if i == 0:
                ax.set_title(label, fontsize=10)
            if label == 'Baseline':
                ax.set_xlabel(f'$\\Delta c$={eb:.2f}', fontsize=8)
            elif label == 'CC-ResDiff':
                ax.set_xlabel(f'$\\Delta c$={ec:.2f}', fontsize=8)
    plt.tight_layout()
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    plt.savefig(args.out, dpi=180, bbox_inches='tight')
    print(f'Wrote {args.out} ({args.mode}, n={len(sel)})')
    for n, eb, ec, d in sel:
        print(f'  {n}: baseline {eb:.3f} -> CC {ec:.3f}  (delta {d:+.3f})')

    all_d = np.array([r[3] for r in rows])
    print(f'\nover all {len(rows)} test images: CC better on '
          f'{(all_d > 0).sum()}/{len(rows)} ({(all_d > 0).mean():.1%}), '
          f'mean delta {all_d.mean():+.4f}')


if __name__ == '__main__':
    main()
