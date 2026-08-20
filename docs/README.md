# Docs

`CC-ResDiff_spec.md` is the original design specification, kept verbatim as a
record of the starting intent. The implementation follows it, but several
findings changed what the work claims. Those divergences are listed here so the
spec is not mistaken for a description of the final result.

## Where the results diverged from the spec

**The headline claim changed from reduction to bounding.** The spec anticipated
a colour-error reduction, and the first run delivered one (-70.6%). Three seeds
showed the baseline's drift is itself seed-dependent, ranging 0.14-0.82 under
identical configurations, while CC-ResDiff lands in 0.15-0.26 every time. The
defensible claim is that the loss *bounds* colour error rather than reducing it
by a fixed amount; the -70.6% figure is the worst-drifting run and overstates
the typical case roughly fivefold.

**"Does colour error improve monotonically with lambda?"** (spec 4.5) --
No. The sweep's colour-error scatter across settings (sd 0.109) is comparable to
the differences between them, so it identifies a usable range (lambda 0.01-0.1,
pool 8) rather than a curve. Pool size 8, the spec's default, is best on every
metric.

**"Does PSNR/SSIM degrade past some threshold?"** (spec 4.5) -- The costs are
real but smaller than first measured. The -0.13 dB PSNR cost in the first run
did not replicate; at n=3 the mean is -0.002 dB and PSNR, SSIM and LPIPS
differences are all within their across-seed spread. FID is the exception:
consistently worse, 4/4 CelebA configurations, and unexplained.

**The `size=8` pooling default was well chosen**, and `lambda_color=0.1` sits in
the usable range -- both as the spec proposed.

## Added beyond the spec

- **Timestep-gradient analysis.** Loss magnitude understates the term's
  influence by ~500x. Its gradient is ~34% of the DDPM gradient and spans five
  orders of magnitude across the trajectory, concentrated at large t.
- **Timestep-reweighting ablation.** Cancelling that concentration removes most
  of the benefit, showing the skew is the mechanism, not an artefact.
- **Colour-transfer baseline.** Post-hoc correction is bounded below by the
  accuracy of the only reference available at inference (0.4358); CC-ResDiff
  reaches 0.2423, below that floor.
- **Evaluation noise floor** (4 seeds on a fixed checkpoint) to separate real
  differences from sampling variance.
- **DIV2K as a second dataset**, and a 25k-image tier with Stage 1 at full
  capacity, to test whether the effect is an artefact of the reduced scale.

## Not implemented

The spec targets SRDiff, and SRDiff is the baseline throughout. ResDiff's own
contributions -- the FD Info Splitter, HF-guided cross-attention, and the
FFT/DWT CNN losses -- are **not** implemented, so no result here should be
compared against ResDiff's published numbers. ResDiff is the motivation (it
names a global colour feature as future work), not the baseline.
