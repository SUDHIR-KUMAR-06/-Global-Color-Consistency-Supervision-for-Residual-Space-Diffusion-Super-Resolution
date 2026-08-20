# CC-ResDiff: Global Color-Consistency Supervision for Residual-Space Diffusion Super-Resolution

## 1. Context / base codebase

Start from the official SRDiff implementation: https://github.com/LeiaLi/SRDiff

That repo implements a two-stage SISR pipeline:
1. **Stage 1 (RRDB)**: a CNN (Residual-in-Residual Dense Block network) trained to
   produce an initial HR prediction `x_cnn` from the LR input.
2. **Stage 2 (Diffusion)**: a DDPM-style U-Net trained to predict the **residual**
   `r = x_HR - x_cnn` via the standard epsilon-prediction objective, conditioned on
   `x_cnn` and the LR image.

At inference, the final HR output is `x_cnn + r_predicted`.

## 2. Problem being addressed

Because the diffusion branch is trained only to predict the high-frequency residual,
it receives weak supervision on **global low-frequency attributes** (overall color
cast, tone, brightness balance). This causes visible color drift in generated images,
especially when the model is undertrained or trained on limited data/compute — exactly
the regime we are working in.

## 3. Proposed method: CC-ResDiff

Add an auxiliary **Global Color-Consistency (GCC) loss** term to Stage 2 (diffusion)
training. It does NOT change the model architecture and adds negligible inference cost
(training-time only).

### 3.1 Core idea

At each training step, in addition to the standard DDPM noise-prediction loss, compute
a loss between the **predicted x0** (i.e., the model's estimate of the clean residual,
reconstructed from its noise prediction at timestep t) and the ground-truth residual,
but restricted to **low-frequency / global color statistics only** — so it penalizes
color/tone drift without competing with the high-frequency detail objective.

### 3.2 Precise formulation

Given:
- `x_t`: noisy residual at timestep t
- `epsilon_theta(x_t, t, x_cnn)`: model's predicted noise (existing SRDiff output)
- `alpha_bar_t`: standard DDPM cumulative product of alphas at t

Reconstruct the predicted clean residual using the standard DDPM closed-form:

```
r_pred_0 = (x_t - sqrt(1 - alpha_bar_t) * epsilon_theta) / sqrt(alpha_bar_t)
```

Reconstruct the model's implied full HR prediction:

```
x_HR_pred = x_cnn + r_pred_0
```

Compute a **downsampled/blurred version** of both the predicted and ground-truth HR
image to isolate low-frequency color content:

```
def low_freq(img, size=8):
    # average-pool to a tiny resolution, discarding high-frequency detail
    return F.adaptive_avg_pool2d(img, output_size=(size, size))

L_color = MSE( low_freq(x_HR_pred), low_freq(x_HR_ground_truth) )
```

`size=8` (8x8 pooled resolution) is a reasonable starting point — small enough to
strip out texture/edge detail, large enough to capture spatial color balance (not just
a single global mean). Treat `size` as a tunable hyperparameter; also try `size=4` and
`size=16` as an ablation.

### 3.3 Total training loss for Stage 2

```
L_total = L_ddpm_noise_mse + lambda_color * L_color
```

- `L_ddpm_noise_mse`: the existing SRDiff/DDPM noise-prediction loss (leave unchanged)
- `lambda_color`: new hyperparameter, start at `lambda_color = 0.1`, sweep over
  `{0.01, 0.1, 0.5, 1.0}` as an ablation to find the best quality/color tradeoff

### 3.4 Where to implement

- Add the `low_freq()` helper and `L_color` computation inside the training step
  function in `tasks/trainer.py` (or wherever the diffusion loss is currently computed
  in the SRDiff repo — locate the function that returns the DDPM MSE loss).
- Expose `lambda_color` and pooling `size` as CLI/config hyperparameters (add to the
  relevant YAML config file, e.g. `configs/diffsr_celeb.yaml`), don't hardcode.
- Do NOT modify Stage 1 (RRDB) training — this is a Stage 2 (diffusion)-only change.
- Do NOT change the model architecture, sampling procedure, or inference code — this
  is a training-loss-only modification, so inference speed must be identical to
  baseline SRDiff.

## 4. Experimental plan (for the paper)

### 4.1 Baseline
Train unmodified SRDiff (as-is from the repo) on a CelebA subset.

### 4.2 Proposed
Train SRDiff + CC-ResDiff (this spec) on the same subset, same seed, same steps.

### 4.3 Scale (compute-constrained settings — must fit a single consumer GPU / Colab T4)
- Dataset: CelebA, subsampled to ~2,000–5,000 training images
- Resolution: 16x16 -> 64x64 (4x), NOT the paper's original 20x20->160x160/64x64->256x256
- Reduce U-Net channel width / depth from default config if needed to fit memory
- Training steps: enough to reach stable convergence on the small subset (monitor loss
  curves; do not assume the original paper's step counts are necessary at this scale)
- Use fp16 / mixed precision
- Checkpoint every N steps to Google Drive (Colab disconnects are expected)

### 4.4 Metrics
- PSNR, SSIM (standard distortion metrics, already in SRDiff eval code)
- FID (already used in ResDiff/SRDiff papers)
- **New metric**: mean color error — e.g., mean absolute difference in average
  per-channel (R,G,B) pixel value between generated and ground-truth HR image,
  averaged over the test set. This directly measures the phenomenon we're fixing.

### 4.5 Ablations
- Sweep `lambda_color` in `{0.01, 0.1, 0.5, 1.0}`
- Sweep pooling `size` in `{4, 8, 16}`
- Report: does color error improve monotonically with `lambda_color`? Does PSNR/SSIM
  degrade past some threshold (tradeoff curve)?

## 5. Deliverables for Claude Code to produce

1. Modified `tasks/trainer.py` (or equivalent) with `L_color` added to the Stage-2
   training loss, gated behind a config flag `use_color_loss: true/false` so baseline
   vs. proposed can be toggled via config, not code changes.
2. New/modified config YAML(s) with `lambda_color` and `color_pool_size` fields.
3. A small evaluation script that computes the new color-error metric alongside
   existing PSNR/SSIM/FID.
4. A Colab-ready notebook or script that: downloads/prepares a CelebA subset, runs
   Stage 1 RRDB training (or loads a pretrained RRDB checkpoint if available), runs
   Stage 2 diffusion training with checkpointing to Drive, and runs evaluation.
