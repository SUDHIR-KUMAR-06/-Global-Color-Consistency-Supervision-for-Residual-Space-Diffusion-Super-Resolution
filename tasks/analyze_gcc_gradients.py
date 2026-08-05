"""
Diagnostic: how much does the GCC term actually steer training?

The loss *values* suggest the auxiliary term is ~0.06% of the DDPM objective at
lambda_color=0.1, but loss magnitude and gradient magnitude are different things
-- a small loss can still steer training if its gradient w.r.t. the parameters is
comparable. This measures the thing that actually matters:

    ||lambda * d L_color / d theta||  vs  ||d L_ddpm / d theta||

over the UNet parameters, per diffusion timestep and aggregated over the uniform
t the trainer actually samples. It also reports what fraction of the predicted
residual is saturated by the [-1, 1] clamp, since clamped elements pass zero
gradient and are the mechanism by which the term goes quiet at large t.

Everything runs in fp32 with autocast off: under AMP the gradients are scaled by
the GradScaler and the raw norms would not be comparable.

Usage:
    python tasks/analyze_gcc_gradients.py --config configs/diffsr_celeb_small_cc.yaml \
        --exp_name diffsr_celebA_small_baseline
"""
import argparse
import json
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, '.')
from utils.hparams import set_hparams, hparams  # noqa: E402


def grad_norm(loss, params):
    """L2 norm of d loss / d params, without disturbing existing .grad buffers."""
    grads = torch.autograd.grad(loss, params, retain_graph=True, allow_unused=True)
    total = 0.0
    for g in grads:
        if g is not None:
            total += float(g.detach().pow(2).sum())
    return total ** 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n_batches', type=int, default=8)
    ap.add_argument('--out', default='checkpoints/gcc_gradient_analysis.json')
    args, _ = ap.parse_known_args()

    set_hparams()
    torch.manual_seed(hparams['seed'])
    np.random.seed(hparams['seed'])

    from models.diffsr_modules import Unet, RRDBNet
    from models.diffusion import GaussianDiffusion
    from tasks.srdiff_celeb import CelebDataSet
    from utils.utils import load_checkpoint, move_to_cuda

    dim_mults = [int(x) for x in hparams['unet_dim_mults'].split('|')]
    denoise_fn = Unet(hparams['hidden_size'], out_dim=3,
                      cond_dim=hparams['rrdb_num_feat'], dim_mults=dim_mults)
    rrdb = RRDBNet(3, 3, hparams['rrdb_num_feat'], hparams['rrdb_num_block'],
                   hparams['rrdb_num_feat'] // 2)
    model = GaussianDiffusion(denoise_fn=denoise_fn, rrdb_net=rrdb,
                              timesteps=hparams['timesteps'],
                              loss_type=hparams['loss_type'])
    opt = torch.optim.Adam(model.parameters(), lr=1e-4)  # only to satisfy the loader
    step = load_checkpoint(model, opt, hparams['work_dir'], prefer_best=True)
    print(f'| analysing checkpoint from step {step}')
    model.eval()

    params = [p for p in denoise_fn.parameters() if p.requires_grad]
    lam = hparams['lambda_color']
    T = hparams['timesteps']

    loader = torch.utils.data.DataLoader(
        CelebDataSet('valid'), batch_size=hparams['eval_batch_size'],
        shuffle=False, num_workers=0)
    batches = []
    for i, b in enumerate(loader):
        if i >= args.n_batches:
            break
        batches.append(move_to_cuda(b))
    print(f'| using {len(batches)} batches of {hparams["eval_batch_size"]}')

    def measure(batch, t_val):
        img_hr, img_lr, img_lr_up = batch['img_hr'], batch['img_lr'], batch['img_lr_up']
        b = img_hr.shape[0]
        t = (torch.randint(0, T, (b,), device=img_hr.device).long() if t_val is None
             else torch.full((b,), t_val, device=img_hr.device).long())
        with torch.no_grad():
            _, cond = rrdb(img_lr, True)
        x_start = model.img2res(img_hr, img_lr_up)
        noise = torch.randn_like(x_start)
        x_t = model.q_sample(x_start=x_start, t=t, noise=noise)
        noise_pred = denoise_fn(x_t, t, cond, img_lr_up)

        if model.loss_type == 'l1':
            l_ddpm = (noise - noise_pred).abs().mean()
        else:
            l_ddpm = F.mse_loss(noise, noise_pred)

        x0 = model.predict_start_from_noise(x_t, t, noise_pred)
        sat = float((x0.detach().abs() > 1).float().mean())
        l_color = model.color_consistency_loss(x0, img_hr, img_lr_up)

        return (float(l_ddpm), float(l_color), sat,
                grad_norm(l_ddpm, params), grad_norm(lam * l_color, params))

    rows = []
    print(f'\n{"t":>6} {"L_ddpm":>9} {"L_color":>11} {"clamped":>8} '
          f'{"|g_ddpm|":>10} {"lam*|g_col|":>12} {"ratio":>9}')
    print('-' * 72)
    for t_val in [0, 10, 25, 50, 75, 99, None]:
        acc = np.array([measure(b, t_val) for b in batches]).mean(axis=0)
        ld, lc, sat, gd, gc = acc
        ratio = gc / gd if gd > 0 else float('nan')
        label = 'random' if t_val is None else str(t_val)
        rows.append({'t': label, 'L_ddpm': ld, 'L_color': lc, 'clamped_frac': sat,
                     'grad_ddpm': gd, 'grad_color_scaled': gc, 'ratio': ratio})
        print(f'{label:>6} {ld:9.5f} {lc:11.3e} {sat:8.1%} {gd:10.4f} {gc:12.3e} {ratio:8.4%}')

    rnd = rows[-1]
    print(f'\nAt lambda_color={lam}, over uniformly sampled t the GCC gradient is '
          f'{rnd["ratio"]:.4%} of the DDPM gradient.')
    for target in (0.01, 0.10, 0.50):
        if rnd['ratio'] > 0:
            print(f'  lambda for a {target:.0%} gradient contribution: '
                  f'{lam * target / rnd["ratio"]:.3g}')

    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump({'lambda_color': lam, 'color_pool_size': hparams['color_pool_size'],
                   'checkpoint_step': step, 'rows': rows}, f, indent=2)
    print(f'\nWrote {args.out}')


if __name__ == '__main__':
    main()
