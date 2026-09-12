# CC-ResDiff: Bounding Seed-Dependent Color Drift in Residual-Space Diffusion Super-Resolution

Residual-space diffusion super-resolution (SRDiff, ResDiff) trains the diffusion
model on the *residual* between a CNN prediction and the ground truth. That
residual is mostly high-frequency, so nothing in the training objective
constrains the absolute color of the output. ResDiff reports the symptom and
proposes "a global color feature" as future work. This repository implements
that proposal as a **Global Color-Consistency (GCC) loss**, and measures what it
actually does.

Paper source and the Word submission are in [`paper/`](paper/); all numeric
results are in [`results/`](results/).

## The finding, stated honestly

The headline is about the **baseline**, not the loss. Across seeds of an
otherwise identical configuration, baseline color error ranges over 0.14-0.82 --
a sixfold spread, orders of magnitude above the 0.0022 evaluation noise floor.
**Single-run comparisons of color-consistency methods are therefore unreliable**,
our own first run included.

Against that variability the GCC loss acts as a *stabiliser* rather than an
improver. Color error across five paired configurations (two datasets, an 8x
range of training-set size):

| run | baseline | CC-ResDiff | change |
|---|---|---|---|
| CelebA 3k, seed A | 0.8234 | 0.2423 | -70.6% |
| CelebA 3k, seed B | 0.3878 | 0.2061 | -46.9% |
| CelebA 3k, seed C | 0.1397 | 0.1461 | +4.6% |
| CelebA 25k | 0.2948 | 0.2555 | -13.3% |
| DIV2K | 0.1650 | 0.2036 | +23.4% |
| **std across runs** | **0.2767** | **0.0426** | |

CC-ResDiff lands in 0.15-0.26 every time; the baseline does not. The benefit on
any given run is governed by how far that run's baseline sits outside
CC-ResDiff's band, which is why one mechanism explains both the -70.6% run and
the DIV2K increase.

**Do not quote -70.6% on its own.** It is the worst-drifting baseline and
overstates the typical case roughly fivefold.

**The costs are real and reported.** PSNR, SSIM and LPIPS are unchanged within
seed noise. FID is consistently *worse* by +2.73 across all four CelebA
configurations, and [an ablation refutes our own explanation for
it](results/README.md#timestep-reweighting-ablation-refuted-hypothesis). The
loss adds no parameters and leaves sampling untouched, so inference cost is
identical to the baseline.

Caveats, in full: [`results/README.md`](results/README.md) and the Limitations
section of the paper. The 25k and DIV2K tiers are single runs.

## What was added to SRDiff

| file | change |
|---|---|
| `models/diffusion.py` | the GCC loss, the fp32/clamped `x0` reconstruction it needs, and optional timestep reweighting |
| `tasks/trainer.py` | early stopping with best-checkpoint tracking, non-finite loss/grad guards, fixed validation averaging |
| `utils/utils.py` | `color_error`, best-checkpoint save/load |
| `tasks/evaluate.py` | standalone evaluation writing `metrics.json` |
| `tasks/run_ablations.py`, `tasks/analyze_gcc_gradients.py`, `tasks/color_transfer_baseline.py` | the ablation sweep, gradient analysis, and post-hoc colour-correction baseline |
| `tools/` | paper tooling: LaTeX checks, LaTeX to Springer Word conversion, Word verification |

The loss itself is small. `models/diffusion.py` reconstructs the implied clean
residual, maps it back to image space, and compares adaptive-average-pooled
color statistics against the ground truth. Two details are load-bearing and are
easy to get wrong: the reconstruction **must** run in fp32 (it amplifies by
~2000x at large `t` and overflows fp16 under AMP), and it **must** be clamped
(unclamped the term reaches 2.8e4 against a DDPM loss of ~0.8).

## Quickstart

Environment and dataset preparation follow SRDiff; see [Upstream
setup](#upstream-setup-srdiff) below. Then, for the CelebA tier used in the
paper:

```bash
PYTHONPATH=. python tasks/trainer.py  --config configs/rrdb/celeb_a_pretrain_small.yaml --exp_name rrdb_celebA_small --reset
PYTHONPATH=. python tasks/trainer.py  --config configs/diffsr_celeb_small.yaml    --exp_name diffsr_celebA_small_baseline --reset --hparams="rrdb_ckpt=checkpoints/rrdb_celebA_small"
PYTHONPATH=. python tasks/trainer.py  --config configs/diffsr_celeb_small_cc.yaml --exp_name diffsr_celebA_small_cc       --reset --hparams="rrdb_ckpt=checkpoints/rrdb_celebA_small"
PYTHONPATH=. python tasks/evaluate.py --config configs/diffsr_celeb_small.yaml    --exp_name diffsr_celebA_small_baseline
PYTHONPATH=. python tasks/evaluate.py --config configs/diffsr_celeb_small_cc.yaml --exp_name diffsr_celebA_small_cc
```

The two arms are identical in data, schedule, seed, initialisation and Stage-1
checkpoint, differing only in `use_color_loss`. Early stopping monitors PSNR,
not color error, so model selection cannot favour the proposed arm.

[`CC_ResDiff_colab.ipynb`](CC_ResDiff_colab.ipynb) runs the same pipeline on a
free Colab GPU.

## Repository map

- `paper/` -- LaTeX source, the Springer Word build, and the submission checklist
- `results/` -- every `metrics.json` the paper cites, plus `results/README.md`
  explaining what each run was and where the numbers diverge from expectation
- `docs/CC-ResDiff_spec.md` -- the original design spec, kept verbatim;
  `docs/README.md` lists where the findings contradicted it
- `tools/` -- `check_tex.py`, `tex2docx.py`, `check_docx.py`
- `configs/` -- the `*_small*` and `*_25k*` configs are ours; the rest are SRDiff's

## Attribution and licensing

This repository is derived from **[SRDiff](https://github.com/LeiaLi/SRDiff)**
by Li et al. Most of the model, data and training code is theirs; the files
listed under "What was added" are the contribution here.

> **Please read before reusing.** The upstream SRDiff repository publishes **no
> license file**. Absent an explicit license, default copyright applies and
> redistribution rights are not granted, so this fork is published for review
> and reproducibility of the results above rather than as freely reusable code.
> If you intend to build on it, seek permission from the SRDiff authors. The
> CC-ResDiff modifications themselves are offered for any academic use with
> attribution.

If you use SRDiff, cite it:

```bib
@article{LI202247,
  title   = {SRDiff: Single image super-resolution with diffusion probabilistic models},
  journal = {Neurocomputing},
  volume  = {479},
  pages   = {47-59},
  year    = {2022},
  issn    = {0925-2312},
  doi     = {10.1016/j.neucom.2022.01.029},
  author  = {Haoying Li and Yifan Yang and Meng Chang and Shiqi Chen and Huajun Feng and Zhihai Xu and Qi Li and Yueting Chen}
}
```

---

## Upstream setup (SRDiff)

### Environment

```bash
python -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
```

### Dataset preparation

1. To download DIV2K, Flickr2K and CelebA, refer to
   https://github.com/andreas128/SRFlow
2. Put them in `data/raw/DIV2K`, `data/raw/Flickr2K`, `data/raw/CelebA`.
3. Pack to pickle for training:

```bash
python data_gen/celeb_a.py --config configs/celeb_a.yaml
python data_gen/df2k.py --config configs/df2k4x.yaml
```

### Pretrained models

https://github.com/LeiaLi/SRDiff/releases/tag/v1.0.0

- CelebA: `srdiff_pretrained_celebA/model_ckpt_steps_300000.ckpt`
- DIV2K: `srdiff_pretrained_div2k/model_ckpt_steps_400000.ckpt`

### Full-scale SRDiff training

```bash
# CelebA
CUDA_VISIBLE_DEVICES=0 python tasks/trainer.py --config configs/rrdb/celeb_a_pretrain.yaml --exp_name rrdb_celebA_1 --reset
CUDA_VISIBLE_DEVICES=0 python tasks/trainer.py --config configs/diffsr_celeb.yaml --exp_name diffsr_celebA_1 --reset --hparams="rrdb_ckpt=checkpoints/rrdb_celebA_1"
CUDA_VISIBLE_DEVICES=0 python tasks/trainer.py --config configs/diffsr_celeb.yaml --exp_name diffsr_celebA_1 --infer

# DIV2K
CUDA_VISIBLE_DEVICES=0 python tasks/trainer.py --config configs/rrdb/df2k4x_pretrain.yaml --exp_name rrdb_div2k_1 --reset
CUDA_VISIBLE_DEVICES=0 python tasks/trainer.py --config configs/diffsr_df2k4x.yaml --exp_name diffsr_div2k_1 --reset --hparams="rrdb_ckpt=checkpoints/rrdb_div2k_1"
CUDA_VISIBLE_DEVICES=0 python tasks/trainer.py --config configs/diffsr_df2k4x.yaml --exp_name diffsr_div2k_1 --infer
```

SRDiff's own reported results, at full scale (not comparable with the reduced
tiers above):

| task | PSNR | SSIM | LPIPS | LR_PSNR |
| :---:| :---:| :---:| :---: | :---:   |
| diffsr_celeb | 25.454 | 0.746 | 0.106 | 53.094 |
| diffsr_div2k | 27.160 | 0.786 | 0.129 | 53.675 |
