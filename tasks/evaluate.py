"""
Evaluation script for CC-ResDiff / SRDiff.

Runs inference over the test split of a trained checkpoint and reports
PSNR, SSIM, LPIPS, LR-PSNR, mean color error (new CC-ResDiff metric) and FID.

Usage (same CLI convention as tasks/trainer.py):
    python tasks/evaluate.py --config configs/diffsr_celeb_small_cc.yaml \
        --exp_name diffsr_celebA_small_cc
"""
import importlib
import json
import random

import numpy as np
import torch

from utils.hparams import hparams, set_hparams


def main():
    set_hparams()
    random.seed(hparams['seed'])
    np.random.seed(hparams['seed'])
    torch.manual_seed(hparams['seed'])
    torch.cuda.manual_seed_all(hparams['seed'])

    hparams['infer'] = True
    hparams['test_save_png'] = True

    pkg = ".".join(hparams["trainer_cls"].split(".")[:-1])
    cls_name = hparams["trainer_cls"].split(".")[-1]
    trainer = getattr(importlib.import_module(pkg), cls_name)()
    trainer.test()

    metrics = {k: trainer.results[k] / trainer.n_samples for k in trainer.metric_keys}
    print('Distortion / perceptual metrics:', {k: round(v, 4) for k, v in metrics.items()})

    gen_dir = trainer.gen_dir
    try:
        from pytorch_fid.fid_score import calculate_fid_given_paths
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        fid_value = calculate_fid_given_paths(
            [f'{gen_dir}/HR', f'{gen_dir}/SR'],
            batch_size=hparams['eval_batch_size'], device=device, dims=2048)
        metrics['fid'] = fid_value
        print('FID:', round(fid_value, 4))
    except ImportError:
        print('pytorch-fid not installed (`pip install pytorch-fid`); skipping FID.')

    out_path = f'{gen_dir}/metrics.json'
    with open(out_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f'Saved metrics to {out_path}')


if __name__ == '__main__':
    main()
