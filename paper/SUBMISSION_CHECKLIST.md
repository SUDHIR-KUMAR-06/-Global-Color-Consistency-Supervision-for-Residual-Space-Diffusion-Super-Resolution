# EACE-2026 submission checklist

`cc_resdiff_eace.tex` is the condensed submission version (~10 pages target).
`cc_resdiff.tex` is the extended draft, kept as the reference for cut material.

## Conference rules, read off the EACE-2026 site on 2026-09-12

Source: <https://www.psit.ac.in/eace2026/>

> "Papers must not exceed 10 pages, include no more than 8 keywords, and follow
> the prescribed format: Times New Roman, 10-point font, double line spacing,
> submitted in Microsoft Word (.doc/.docx) format."

Springer LNEE formatting guidelines apply; the Word template is the one in
`~/Downloads/Word_Template/` (`splnproc1703.docm`, or `_mac` for Word for Mac
2016 -- the macros do **not** work in Word for Mac 2011).

| milestone | date |
|---|---|
| paper submission | **15 Sep 2026** |
| acceptance notification | 25 Sep 2026 |
| camera-ready | 30 Sep 2026 |
| registration deadline | 10 Oct 2026 |
| conference | 20-21 Nov 2026 |

Upload at <https://proconf.org/events/index.php?url=eace-2026>. The
first/corresponding author must register the paper or it is withdrawn from the
proceedings.

Current compliance: abstract 248 words (Springer wants 150-250), 8 keywords
(exactly at the cap), ~8.9 pages estimated. The Word file is built and checked --
see "The Word file" below.

## Springer template header, from `splnproc1703.docm`

`tools/tex2docx.py` writes these styles directly, so this table is reference
rather than instructions -- it is what to check against if the layout ever looks
wrong, and what to follow if you end up styling anything by hand.

| style | content |
|---|---|
| `papertitle` | contribution title |
| `author` | `First Author1[ORCID] and Second Author2[ORCID]` |
| `address` | one line per affiliation, e-mail on the last line |
| `abstract` | macro prepends "Abstract."; 150-250 words |
| `keywords` | macro prepends "Keywords:"; comma separated, closing period |

Only heading levels 1 and 2 are numbered; levels 3 and 4 are unnumbered run-in
headings (bold and italic respectively). References are numbered and cited as
`[1]`, in Springer style: `Author, F.: Article title. Journal 2(5), 99-110
(2016).` Insert Greek letters and symbols via Insert -> Symbol, never by typing
them, or reformatting can silently drop them.

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

## Authors -- added 2026-09-12

Author block now reads:

    Sudhir Kumar(1) and Sanjoy Chattopadhyay(2)
    snghsudhirkumar06@gmail.com   chattopadhyaysanjoy18@gmail.com

Two things to confirm before submitting:

- **The second author's display name is inferred from the e-mail address**, not
  supplied. Confirm the spelling they publish under.
- **Both affiliations are still `TODO`.** Springer wants department, institution,
  city, postcode and country on the `address` line. If both authors share one
  affiliation, collapse to a single unnumbered `address` line and drop the
  superscripts.

Optional: add ORCID ids as `[0000-1111-2222-3333]` superscripts after each name.
They are not printed in the book, but in the eBook they become links to the
ORCID profile.

Abstract is 248 words.

Also fixed during the Word conversion: Section 3 read "Pooling is what makes
Eq. 3 complementary rather than redundant: texture and edges, retaining only the
spatial color balance...". The condensing pass had dropped "at $k=8$ it
discards", leaving the sentence without a verb. Restored from `cc_resdiff.tex`.

## The Word file

`paper/Kumar_CC-ResDiff.docx` is built from the .tex by
`tools/tex2docx.py`, which writes straight into the styles of
`splnproc1703.docm`. **Edit the .tex and re-run the converter; do not hand-edit
the .docx**, or the two drift apart.

```bash
python tools/tex2docx.py && python tools/check_docx.py paper/Kumar_CC-ResDiff.docx
```

`tools/check_docx.py` verifies the parts are well-formed, every relationship
resolves, every style name exists, and no LaTeX residue survived, then estimates
the length by laying the text out with real Times New Roman metrics:
**~8.9 pages, inside the 10-page limit.** Section and reference numbers come
from the template's own numbering, and the table, figure and equation numbers
are SEQ fields, so all of them renumber themselves if you move things.

Still to check once you have Word in front of you -- none of this is verifiable
without it:

- Open it and press Ctrl+A then F9 to refresh the SEQ fields.
- Look at the four equations. They are real OMML, built by hand from the LaTeX,
  so they are editable in Word's equation editor -- but nothing here has
  rendered them.
- Confirm the real page count against the ~8.9 estimate. Word justifies and
  hyphenates; the estimate does neither, so treat it as +/- half a page.
- The macro ribbon is deliberately absent: the .docx is stripped of the
  template's VBA so it is a plain .docx, not a macro file. The styles are all
  still there, so apply them from the Styles pane if you need to.

## MUST DO BEFORE SUBMITTING -- I could not do these here

1. **Fill in both affiliations, and confirm the second author's name.** Marked
   `TODO` in the author block; emails are filled in. Re-run the converter after.
2. **Verify every bibliography entry.** They were drafted from memory. Titles and
   authors are believed correct; venues, years and page numbers are NOT checked.
   Verify most carefully: SR3 (TPAMI volume/year), Perception Prioritized
   Training (author list), Min-SNR (author list).
3. **Resolve the spacing contradiction with the organisers.** The call says
   "double line spacing"; the Springer LNEE template it also mandates is
   single-spaced with a fixed 12.2 x 19.3 cm text area, and its macros set
   spacing themselves. These cannot both hold. Ask which governs the 10-page
   count -- it roughly halves what fits. If double-spacing wins, a further cut
   is needed: take it from the ablation table, then the gradient discussion.
   Until they answer, build the Word file with the template's own spacing; that
   is the version the proceedings are typeset from.
4. **Relabel the seeds.** Table 1 lists "seed A/B/C"; B was an independently
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
