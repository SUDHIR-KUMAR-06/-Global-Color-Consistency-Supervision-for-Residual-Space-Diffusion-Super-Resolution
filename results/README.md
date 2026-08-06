# CC-ResDiff results

Numeric results for the CC-ResDiff experiments. `checkpoints/` is gitignored, so
these are copied here to keep the data with the code.

Reproduce with the commands in `CC_ResDiff_colab.ipynb`, or locally:

```bash
PYTHONPATH=. python tasks/trainer.py  --config configs/rrdb/celeb_a_pretrain_small.yaml --exp_name rrdb_celebA_small --reset
PYTHONPATH=. python tasks/trainer.py  --config configs/diffsr_celeb_small.yaml    --exp_name diffsr_celebA_small_baseline --reset --hparams="rrdb_ckpt=checkpoints/rrdb_celebA_small"
PYTHONPATH=. python tasks/trainer.py  --config configs/diffsr_celeb_small_cc.yaml --exp_name diffsr_celebA_small_cc       --reset --hparams="rrdb_ckpt=checkpoints/rrdb_celebA_small"
PYTHONPATH=. python tasks/evaluate.py --config configs/diffsr_celeb_small.yaml    --exp_name diffsr_celebA_small_baseline
PYTHONPATH=. python tasks/evaluate.py --config configs/diffsr_celeb_small_cc.yaml --exp_name diffsr_celebA_small_cc
```

## Files

| file | what it is |
|---|---|
| `metrics_diffsr_celebA_small_{baseline,cc}.json` | CelebA test set, 300 images, best checkpoints |
| `metrics_diffsr_div2k_small_{baseline,cc}.json` | DIV2K test set, 512 tiles, best checkpoints |
| `noise_floor_celeba.json` | same CelebA baseline checkpoint evaluated under 4 seeds |
| `ablations.csv` / `ablations.json` | 7-run sweep at a 5000-step budget |
| `gcc_gradient_analysis.json` | GCC vs DDPM gradient ratio per timestep |

## Main comparison

Both arms are identical apart from `use_color_loss`; same data, schedule, seed and
RRDB checkpoint. Arrows mark the better arm.

| metric | CelebA base | CelebA CC | | DIV2K base | DIV2K CC | |
|---|---|---|---|---|---|---|
| color_error | 0.8234 | **0.2423** | -70.6% | **0.1650** | 0.2036 | +23.4% |
| lr_psnr | 43.690 | **44.509** | +0.82 | **47.248** | 47.101 | -0.15 |
| psnr | **25.095** | 24.967 | -0.13 | 29.650 | **29.703** | +0.05 |
| ssim | **0.8144** | 0.8123 | -0.002 | 0.7635 | **0.7646** | +0.001 |
| lpips | 0.0466 | **0.0459** | -0.0007 | **0.2570** | 0.2630 | +0.006 |
| fid | **69.32** | 73.23 | +3.90 | **82.71** | 83.25 | +0.54 |

**The CelebA result does not replicate on DIV2K.** Every sign flips except FID,
which is worse on both. The most likely reason is headroom: DIV2K's baseline
color error is already 5x lower than CelebA's (0.165 vs 0.823), so there is
little global colour drift for the GCC loss to correct and it contributes a
small regression instead. The supportable claim is therefore conditional --
*where* a residual diffusion model drifts in colour, GCC supervision
substantially reduces it -- not that it helps universally.

Calibrated against the CelebA evaluation noise floor, the color_error gain
(268 sigma) and LR-PSNR gain (87 sigma) are unambiguous, the PSNR/SSIM costs and
the FID regression are real but small (5-25 sigma), and the LPIPS difference is
not significant (0.5 sigma).

## Ablations (CelebA, 5000-step budget)

Ablation runs are comparable to each other, never to the full-length runs above.

lambda sweep at pool 8:

| lambda | color_err | psnr | lpips | fid | lr_psnr |
|---|---|---|---|---|---|
| none | 0.4833 | 23.857 | **0.0612** | 111.51 | 41.445 |
| 0.01 | 0.3382 | **23.955** | 0.0635 | **109.11** | **41.918** |
| 0.1 | **0.1952** | 23.941 | 0.0653 | 110.43 | 41.865 |
| 0.5 | 0.4985 | 23.721 | 0.0665 | 115.43 | 41.192 |
| 1.0 | 0.2162 | 23.727 | 0.0680 | 116.71 | 40.976 |

pool sweep at lambda 0.1:

| pool | color_err | psnr | lpips | fid |
|---|---|---|---|---|
| 4 | 0.3385 | 23.839 | 0.0641 | 112.47 |
| 8 | **0.1952** | **23.941** | 0.0653 | **110.43** |
| 16 | 0.3522 | 23.919 | 0.0658 | 111.05 |

Pool size 8 wins on every metric. 5 of 6 GCC arms beat the no-GCC reference on
color_error, and LPIPS degrades monotonically with lambda while FID and LR-PSNR
worsen past lambda=0.01 -- the cost side is consistent.

**These runs do not resolve a lambda optimum.** color_error across the six GCC
arms has stdev 0.109, comparable to the differences between settings, and the
lambda=0.5 point is out of line with both its neighbours. The sweep supports a
usable range (lambda 0.01-0.1, pool 8), not a dose-response curve; drawing one
through single points would overstate it. Each setting needs 2-3 repeats.

## Gradient analysis

Loss values suggest the GCC term is negligible (~0.06% of the DDPM loss at
lambda=0.1). Its *gradient* is ~34% of the DDPM gradient, and the contribution is
extremely uneven across timesteps:

| t | grad ratio | fraction of x0 clamped |
|---|---|---|
| 0 | 0.002% | 0.4% |
| 50 | 0.40% | 0.1% |
| 75 | 1.28% | 0.1% |
| 99 | **235.7%** | 97.4% |
| uniform t | **33.9%** | 1.5% |

The [-1,1] clamp bounds the loss value but not the gradient: at t=T-1 almost
everything saturates, yet the rest still carries the ~2000x 1/sqrt(alpha_bar)
amplification. In effect this is a high-t colour loss with a heavy-tailed
contribution, which also explains why large lambda degrades the primary
objective -- at lambda=0.5 the auxiliary term would be ~170% of the DDPM
gradient.

## Training stability

Non-finite gradient norms per run, all caught and skipped, with zero non-finite
losses in any run:

| run | steps | skipped |
|---|---|---|
| CelebA baseline | 20000 | 8 |
| CelebA CC | 16000 (early stop) | 6 |
| DIV2K baseline | 20000 | 7 |
| DIV2K CC | 20000 | 8 |

This is ordinary AMP behaviour -- `GradScaler` probes for the largest workable
loss scale and backs off on overflow -- not instability, and the rate is
unaffected by the GCC loss.

## Known limitations

- **Single training seed per arm.** Everything above is calibrated against
  evaluation noise, which is a lower bound on total variance. The large
  color_error effect should replicate; the small PSNR and FID deltas may not.
- **No DIV2K noise floor**, so the +23.4% color_error regression there is not
  established as real.
- **FID sample counts are small** (300 CelebA, 512 DIV2K); biased upward and
  usable only as a relative comparison on identical images.
- **DIV2K metrics cover image interiors.** Partial edge tiles are dropped at
  packing time, so the bottom 124 rows and right 248 columns of each 2040x1404
  image are excluded.
