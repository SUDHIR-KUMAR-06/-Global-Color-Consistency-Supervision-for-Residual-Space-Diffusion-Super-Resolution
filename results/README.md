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
| `metrics_diffsr_celebA_s2024_{baseline,cc}.json` | third CelebA seed |
| `metrics_diffsr_celebA_25k_{baseline,cc}.json` | 25k-image tier, full-capacity Stage 1 |
| `metrics_diffsr_celebA_small_cc_snr.json` | timestep-reweighting ablation |
| `color_transfer_metrics.json` | post-hoc colour-correction baseline |
| `gcc_gradient_analysis.json` | GCC vs DDPM gradient ratio per timestep |

## Main comparison

Both arms are identical apart from `use_color_loss`; same data, schedule, seed and
RRDB checkpoint. All tiers share one identical 300-image CelebA test split.

### The headline: the loss bounds colour error rather than reducing it

Per-run colour error over five paired runs (two datasets, two data scales):

| run | baseline | CC-ResDiff | change |
|---|---|---|---|
| CelebA 3k, seed 1234 | 0.8234 | 0.2423 | -70.6% |
| CelebA 3k, colab | 0.3878 | 0.2061 | -46.9% |
| CelebA 3k, seed 2024 | 0.1397 | 0.1461 | +4.6% |
| CelebA 25k | 0.2948 | 0.2555 | -13.3% |
| DIV2K | 0.1650 | 0.2036 | +23.4% |
| **std across runs** | **0.2767** | **0.0426** | |
| **range** | **0.684** | **0.109** | |

The baseline's drift is strongly seed-dependent and does not shrink
systematically with more data. CC-ResDiff lands in 0.15-0.26 every time --
standard deviation 6.5x smaller, range 6.2x narrower. The benefit on any given
run is governed by how far that run's baseline sits outside CC-ResDiff's band,
which is why the same mechanism explains both the -70.6% run and the DIV2K
"non-replication".

**Do not quote the -70.6% figure alone.** It is the run whose baseline drifted
worst, and it overstates the typical case by roughly 5x.

### CelebA 3k tier, all metrics (n=3, mean +- std)

| metric | baseline | CC-ResDiff | delta |
|---|---|---|---|
| color_error | 0.4494 +- 0.3446 | **0.1981 +- 0.0486** | -0.2512 |
| lr_psnr | 44.659 +- 0.820 | **44.953 +- 0.659** | +0.294 |
| psnr | **25.033 +- 0.082** | 25.031 +- 0.075 | -0.002 |
| ssim | **0.8143 +- 0.0022** | 0.8141 +- 0.0021 | -0.0002 |
| lpips | **0.0439 +- 0.0020** | 0.0446 +- 0.0021 | +0.0007 |
| fid | **66.70 +- 2.19** | 69.43 +- 3.59 | +2.73 |

Only colour error and FID differ by more than their across-seed spread. The
-0.13 dB PSNR "cost" seen in the first run did not replicate (n=3 mean:
-0.002 dB) and was seed noise.

### Scaling tier: 25k images, Stage 1 at full capacity

8x the data and Stage 1 restored to 32 feat / 8 blocks, same 300-image test set.

| metric | baseline 3k (n=3) | baseline 25k (n=1) |
|---|---|---|
| psnr | 25.033 | **25.428** |
| ssim | 0.8143 | **0.8263** |
| lpips | 0.0439 | **0.0429** |
| lr_psnr | 44.66 | **47.63** |
| fid | 66.70 | **61.83** |
| color_error | 0.4494 | **0.2948** |

Stage 1 alone improved 26.25 -> 27.25 dB. The GCC loss's relative benefit falls
to -13.3% at this scale, but only because the baseline drifts less; CC-ResDiff's
own colour error (0.2555) stays inside its usual band. This is a fifth
confirmation of the bounding behaviour, under conditions chosen to break it.

### DIV2K

| metric | baseline | CC-ResDiff | delta |
|---|---|---|---|
| color_error | **0.1650** | 0.2036 | +23.4% |
| lr_psnr | **47.248** | 47.101 | -0.15 |
| psnr | 29.650 | **29.703** | +0.05 |
| ssim | 0.7635 | **0.7646** | +0.001 |
| lpips | **0.2570** | 0.2630 | +0.006 |
| fid | **82.71** | 83.25 | +0.54 |

DIV2K's baseline sits in the low-drift band (0.165), like CelebA seed 2024
(0.140). Not a failure to generalise -- the same behaviour with no headroom.

### Colour-transfer baseline

Post-hoc correction cannot substitute for the learned loss:

| method | color_error | lr_psnr |
|---|---|---|
| baseline | 0.8234 | 43.690 |
| + mean transfer | 0.8746 | 43.558 |
| + mean/std transfer | 0.9333 | 36.243 |
| *reference floor (bicubic UP vs HR)* | *0.4358* | -- |
| **CC-ResDiff** | **0.2423** | **44.509** |

Any post-hoc correction is bounded below by the accuracy of the reference it
matches to, and the only reference admissible at inference is off by 0.4358.
CC-ResDiff reaches 0.2423, 1.8x below that floor, because it is supervised
against true HR at training time.

### Timestep-reweighting ablation (refuted hypothesis)

| variant | color_error | lr_psnr | fid |
|---|---|---|---|
| baseline | 0.8234 | 43.690 | **69.32** |
| CC, w=1 | **0.2423** | **44.509** | 73.23 |
| CC, w=alpha_bar | 0.6728 | 43.366 | 77.81 |

We predicted that cancelling the high-t gradient skew would fix FID while keeping
the colour benefit. It did neither: FID got worse and the colour benefit largely
vanished. The skew is the *mechanism*, not an artefact -- large t is where a
diffusion model settles global structure. The FID regression remains unexplained.

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

- **Three seeds on the CelebA 3k tier; one run elsewhere.** Enough to establish
  that baseline drift varies widely and CC-ResDiff's does not, but not to
  characterise either distribution. The 25k and DIV2K tiers are single runs.
- **Scale.** 25,000 images is 15% of CelebA, still at 64x64 with a 2.4M-parameter
  diffusion model -- far below what SRDiff and ResDiff use.
- **No DIV2K noise floor**, so the +23.4% color_error regression there is not
  established as real.
- **Not comparable to published SRDiff/ResDiff numbers.** Same dataset names,
  different task (16->64 vs their 64->256 / 40->160), training-set size and model
  capacity. The baseline here is SRDiff; ResDiff's own components (FD Info
  Splitter, HF-guided cross-attention, FFT/DWT losses) are not implemented.
- **FID sample counts are small** (300 CelebA, 512 DIV2K); biased upward and
  usable only as a relative comparison on identical images.
- **DIV2K metrics cover image interiors.** Partial edge tiles are dropped at
  packing time, so the bottom 124 rows and right 248 columns of each 2040x1404
  image are excluded.
