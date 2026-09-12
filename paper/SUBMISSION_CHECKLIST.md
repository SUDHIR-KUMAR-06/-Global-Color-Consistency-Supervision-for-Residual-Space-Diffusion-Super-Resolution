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
(exactly at the cap), 10 pages rendered (the cap). The Word file is built and
checked -- see "The Word file" below.

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

## Authors -- confirmed 2026-09-12

    Sudhir Kumar[0009-0007-0878-0231] and Sanjoy Chattopadhyay[0009-0008-0937-6676]
    Pranveer Singh Institute of Technology, Kanpur 209305, Uttar Pradesh, India
    snghsudhirkumar06@gmail.com, sanjoyrsearch@gmail.com

Sudhir Kumar is first and corresponding author, and must be the one who
registers the paper -- EACE withdraws papers the corresponding author has not
registered.

Both authors are at PSIT, so the affiliation is one unnumbered `address` line
with no superscript numerals, per Springer's convention for a shared
affiliation. Two deliberate omissions:

- **No job titles.** "Assistant Professor" is not part of a Springer author
  block; the address line carries the institution, not the post.
- **No department.** The template's own sample addresses give institution, city,
  postcode and country and no department, so this is complete as it stands. To
  name one (CSE or ECE), put it before the institution in the `\author` block
  and re-run the converter.

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
resolves, every style name exists, no LaTeX residue survived, and every
non-ASCII character exists in the font its own run asks for. It then renders
with LibreOffice and counts pages for real: **10 pages, exactly at the limit,
with 11.6 cm spare on the last page.** That slack is the margin of safety --
Word may break a line or two differently, but not half a page's worth.

To regenerate the PDF (for your own checking; the submission is the .docx):

```bash
soffice --headless --convert-to pdf --outdir paper paper/Kumar_CC-ResDiff.docx
```

## The LaTeX build

MiKTeX is installed (`winget install MiKTeX.MiKTeX`, user scope, with
`[MPM]AutoInstall=1` so missing packages fetch themselves). From `paper/`, run
pdflatex **twice** -- there is no BibTeX step, the bibliography is a
`thebibliography` block, but cross-references need the second pass:

```bash
pdflatex -interaction=nonstopmode cc_resdiff_eace.tex && pdflatex -interaction=nonstopmode cc_resdiff_eace.tex
```

That produces `paper/cc_resdiff_eace.pdf`, also 10 pages. The `.tex` now carries
Springer's page geometry (A4, 12.2 x 19.3 cm text block), so the LaTeX build
paginates like the Word file instead of like US Letter.

**Three PDFs are not three candidate submissions.** EACE accepts Word only:

| file | what it is |
|---|---|
| `Kumar_CC-ResDiff.docx` | **the submission** |
| `Kumar_CC-ResDiff.pdf` | that .docx rendered -- what the reviewers will see |
| `cc_resdiff_eace.pdf` | the LaTeX build -- a reading copy, `article` class, not Springer's styles |

Two size commands in the `\author` block (`\normalsize`) and on the address
lines (`\small`) exist only for the LaTeX build: `article` sets authors at 12 pt,
where Springer's style is 10 pt, and the names plus both ORCIDs overrun the
column at 12 pt. `tex2docx.py` strips them, so the Word output is unaffected.

### Two decisions worth knowing about

**Caption and equation numbers are literal text, not SEQ fields.** The Springer
macro uses fields so Word renumbers when you move things. We do not need that --
the .tex is the source of truth and every number is recomputed on each build --
and the fields actively break the PDF: LibreOffice re-evaluates SEQ on load and
resets every one to 1, so a field version exports as "Table 1" five times and
"(1)" four times. The cost: reordering tables *inside Word* will not renumber
them. Reorder in the .tex instead.

**Section and reference numbers still come from the template's own numbering**,
which both Word and LibreOffice handle correctly.

Still to check once you have Word in front of you:

- The four equations are real OMML, editable in Word's equation editor. They
  render correctly in LibreOffice; Word uses Cambria Math where LibreOffice
  substitutes Liberation Serif, so expect them to look slightly better, not
  worse.
- Confirm the page count is still 10.
- The macro ribbon is deliberately absent: the .docx is stripped of the
  template's VBA so it is a plain .docx, not a macro file. The styles are all
  still there, so apply them from the Styles pane if you need to.

## MUST DO BEFORE SUBMITTING -- I could not do these here

1. **Resolve the spacing contradiction with the organisers.** The call says
   "double line spacing"; the Springer LNEE template it also mandates is
   single-spaced with a fixed 12.2 x 19.3 cm text area, and its macros set
   spacing themselves. These cannot both hold. Ask which governs the 10-page
   count -- it roughly halves what fits. If double-spacing wins, a further cut
   is needed: take it from the ablation table, then the gradient discussion.
   Until they answer, build the Word file with the template's own spacing; that
   is the version the proceedings are typeset from.
2. **Relabel the seeds.** Table 1 lists "seed A/B/C"; B was an independently
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
