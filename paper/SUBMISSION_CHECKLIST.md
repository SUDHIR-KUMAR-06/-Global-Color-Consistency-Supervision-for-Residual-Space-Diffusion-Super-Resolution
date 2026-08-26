# EACE-2026 submission checklist

`cc_resdiff_eace.tex` is the condensed submission version (~10 pages target).
`cc_resdiff.tex` is the extended draft, kept as the reference for cut material.

## Done

- Condensed: 18 subsections -> 5; 9 tables -> 5; 3 figures -> 1.
- Restructured to lead with the seed-variance finding, which is the strongest
  and most transferable result, rather than burying it in the results.
- Abstract 355 -> 253 words, with the FID regression stated explicitly rather
  than left for the reader to discover in the experiments.
- Title changed to name the actual claim: "Bounding Seed-Dependent Color Drift".
- "guarantee" softened to "a consistent stabilising effect in our experiments";
  five paired runs do not establish a formal guarantee.
- Keywords added (8).
- Repaired a mangled `\times` that rendered as "6.2imes".
- Reworded the algorithm cross-reference, which two readers reported as
  "Figure Figure 1". The source did not contain that duplication, but the
  rewording removes any possibility of it.
- Scope paragraph states that the baseline is SRDiff, that ResDiff is not
  reimplemented, and that absolute numbers are not comparable with published
  SRDiff/ResDiff/SR3 results.

## Second review round -- applied

- Equations rewritten for robustness: the x0 reconstruction now uses `rac`
  rather than an inline `ig/`, and the GCC loss and total objective are two
  separate numbered displays instead of one crowded line. (The reported
  "formatting artifacts" were most likely PDF text-extraction noise -- math
  rarely survives extraction -- but the cleaner form is worth having regardless.)
- Figure 1 moved from the end of the paper into Section 4, immediately after the
  main results, with `[htbp]` so it places inline rather than floating past the
  references.
- Softened "whether a residual diffusion model drifts in color is substantially a
  matter of chance" to "under the evaluated configuration, whether substantial
  color drift occurs is strongly influenced by the random training seed".
- "five paired runs" -> "five paired experimental configurations", and the text
  now states explicitly that the three-seed CelebA experiment is the only
  replicated evidence, with the 25k and DIV2K tiers being single runs. They are
  no longer presented as five equally strong confirmations.

Abstract is 254 words. Still verify the compiled page count and the equation
rendering visually -- neither is checkable without a LaTeX toolchain here.

## MUST DO BEFORE SUBMITTING -- I could not do these here

1. **Convert to .doc/.docx.** The conference requires it. Neither pandoc nor a
   LaTeX toolchain is installed on this machine, so no conversion was possible
   and the compiled page count is unverified. Equations will need Word equation
   objects; the five tables convert cleanly.
2. **Apply the official EACE / Springer LNEE template.** The preamble here is
   plain `article` and is a placeholder.
3. **Fill in affiliation and email.** Marked `TODO` in the author block.
4. **Verify every bibliography entry.** They were drafted from memory. Titles and
   authors are believed correct; venues, years and page numbers are NOT checked.
   Verify most carefully: SR3 (TPAMI volume/year), Perception Prioritized
   Training (author list), Min-SNR (author list).
5. **Confirm the spacing rule with the organisers.** Single- vs double-spacing
   roughly halves what fits in 10 pages. If double-spacing governs, a further
   cut is needed -- take it from the ablation table and the gradient discussion,
   in that order.
6. **Relabel the seeds.** Table 1 lists "seed A/B/C"; B was an independently
   executed Colab run whose seed value should be recorded accurately.

## If a further cut is needed, in order of what to drop

1. Ablation table -> keep only the lambda rows, move pool sizes to a sentence.
2. Gradient table -> state the three numbers inline; drop the table.
3. Post-hoc colour-transfer table -> compress to two sentences with the floor
   argument, which is the part that matters.
4. Do NOT cut: Table 1 (per-run colour error), the scope paragraph, or the FID
   trade-off statement. Those are what make the paper defensible.

## Reviewer concerns not yet addressed

- **Scale.** Largest run is 25k CelebA images at 64x64. A reviewer may ask for
  the full SRDiff/ResDiff setting; the paper states this limitation rather than
  answering it.
- **25k and DIV2K tiers are n=1.** Given baseline drift varies sixfold by seed,
  one run cannot place either tier within the band. Two more seeds at 25k is the
  single highest-value remaining experiment (~4 GPU-hours).
- **FID regression is unexplained.** Reported honestly, with the refuting
  ablation, but a reviewer may still consider it disqualifying.
