"""
Colour-transfer post-processing baseline.

The obvious objection to a learned colour-consistency loss is that a few lines
of post-processing might do the same job for free. This implements that
objection as a baseline: take the trained *baseline* model's outputs and correct
their colour statistics afterwards, then score them the same way.

Crucially this may only use information available at inference. Matching to the
ground truth would trivially minimise color_error while being unusable in
practice, so the reference is the bicubic-upsampled LR input -- the same signal
the network itself is conditioned on. Two variants:

  mean      : shift each channel so its mean matches the reference
  mean_std  : match each channel's mean and standard deviation (Reinhard-style)

Both operate per image, per channel, in RGB.

Usage (after evaluating the baseline arm, whose PNGs it reads):
    python tasks/color_transfer_baseline.py \
        --config configs/diffsr_celeb_small.yaml \
        --exp_name diffsr_celebA_small_baseline
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import torch
from PIL import Image
from tqdm import tqdm

sys.path.insert(0, '.')
from utils.hparams import set_hparams, hparams  # noqa: E402


def transfer(sr, ref, mode):
    """Match sr's per-channel colour statistics to ref's. Both uint8 HWC."""
    out = sr.astype(np.float64)
    ref = ref.astype(np.float64)
    for c in range(3):
        s, r = out[..., c], ref[..., c]
        if mode == 'mean':
            out[..., c] = s + (r.mean() - s.mean())
        elif mode == 'mean_std':
            ss = s.std()
            # a flat channel has no scale to match; shifting is all that is defined
            out[..., c] = (s - s.mean()) * (r.std() / ss if ss > 1e-6 else 1.0) + r.mean()
        else:
            raise ValueError(mode)
    return np.clip(out, 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', default='both', choices=['mean', 'mean_std', 'both'])
    ap.add_argument('--out', default=None)
    args, _ = ap.parse_known_args()

    set_hparams()
    from utils.utils import Measure

    work_dir = hparams['work_dir']
    gen_dirs = sorted(glob.glob(f'{work_dir}/results_*'))
    assert gen_dirs, f'no results_* under {work_dir}; run tasks/evaluate.py first'
    gen_dir = gen_dirs[-1]
    print(f'| reading generated images from {gen_dir}')

    sr_paths = sorted(glob.glob(f'{gen_dir}/SR/*.png'))
    assert sr_paths, f'no SR pngs in {gen_dir}/SR'
    for sub in ('HR', 'LR', 'UP'):
        assert os.path.isdir(f'{gen_dir}/{sub}'), f'missing {gen_dir}/{sub}'
    print(f'| {len(sr_paths)} images')

    measure = Measure()
    sr_scale = hparams['sr_scale']
    modes = ['mean', 'mean_std'] if args.mode == 'both' else [args.mode]
    results = {}

    for mode in modes:
        out_dir = f'{gen_dir}/SR_ct_{mode}'
        os.makedirs(out_dir, exist_ok=True)
        acc, n = {}, 0
        for p in tqdm(sr_paths, desc=f'colour transfer [{mode}]'):
            name = os.path.basename(p)
            sr = np.array(Image.open(p).convert('RGB'))
            hr = np.array(Image.open(f'{gen_dir}/HR/{name}').convert('RGB'))
            up = np.array(Image.open(f'{gen_dir}/UP/{name}').convert('RGB'))
            lr = np.array(Image.open(f'{gen_dir}/LR/{name}').convert('RGB'))

            fixed = transfer(sr, up, mode)
            Image.fromarray(fixed).save(f'{out_dir}/{name}')

            s = measure.measure(fixed.transpose(2, 0, 1),
                                hr.transpose(2, 0, 1),
                                lr.transpose(2, 0, 1), sr_scale)
            for k, v in s.items():
                acc[k] = acc.get(k, 0.0) + v
            n += 1

        metrics = {k: v / n for k, v in acc.items()}
        try:
            from pytorch_fid.fid_score import calculate_fid_given_paths
            dev = 'cuda' if torch.cuda.is_available() else 'cpu'
            metrics['fid'] = calculate_fid_given_paths(
                [f'{gen_dir}/HR', out_dir], batch_size=16, device=dev, dims=2048)
        except ImportError:
            print('| pytorch-fid missing; skipping FID')
        results[f'colour_transfer_{mode}'] = metrics
        print(f'| {mode}: ' + str({k: round(v, 4) for k, v in metrics.items()}))

    out_path = args.out or f'{gen_dir}/color_transfer_metrics.json'
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f'\nWrote {out_path}')


if __name__ == '__main__':
    main()
