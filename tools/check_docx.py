"""
Structural check on the Word file produced by tools/tex2docx.py.

There is no Word on this machine, so "it converted" is not evidence that it
opens. This verifies the things that would otherwise only surface when the
submission portal or a reviewer opens the file:

  * every part is well-formed XML, and every r:embed / r:id resolves
  * every w:pStyle and w:rStyle names a style that exists in styles.xml
  * no LaTeX residue (stray backslash macros, $, ~, unresolved ?? refs)
  * the header block, section order and counts match the .tex
  * an estimate of the page count, which is the number that decides whether
    the paper still fits EACE's 10-page limit

Usage:
    python tools/check_docx.py paper/Kumar_CC-ResDiff.docx
"""
import argparse
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
M = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'

TWIP = 20.0               # twips per point


def page_box(doc):
    """Text width and height in points, from the document's own sectPr."""
    s = doc.find('.//' + W + 'sectPr')
    sz = s.find(W + 'pgSz')
    mar = s.find(W + 'pgMar')
    w = (int(sz.get(W + 'w')) - int(mar.get(W + 'right'))
         - int(mar.get(W + 'left'))) / TWIP
    h = (int(sz.get(W + 'h')) - int(mar.get(W + 'top'))
         - int(mar.get(W + 'bottom'))) / TWIP
    return w, h


def style_metrics(styles_xml):
    """styleId -> (size_pt, leading_pt, before_pt, after_pt), basedOn resolved."""
    root = ET.fromstring(styles_xml)
    raw, based = {}, {}
    for s in root.iter(W + 'style'):
        sid = s.get(W + 'styleId')
        sz = s.find('./' + W + 'rPr/' + W + 'sz')
        sp = s.find('./' + W + 'pPr/' + W + 'spacing')
        bo = s.find('./' + W + 'basedOn')
        raw[sid] = (
            int(sz.get(W + 'val')) / 2.0 if sz is not None else None,
            int(sp.get(W + 'line')) / TWIP
            if sp is not None and sp.get(W + 'line') else None,
            int(sp.get(W + 'before')) / TWIP
            if sp is not None and sp.get(W + 'before') else 0.0,
            int(sp.get(W + 'after')) / TWIP
            if sp is not None and sp.get(W + 'after') else 0.0,
        )
        based[sid] = bo.get(W + 'val') if bo is not None else None

    def resolve(sid, seen=()):
        size, lead, bef, aft = raw.get(sid, (None, None, 0.0, 0.0))
        parent = based.get(sid)
        if parent and parent not in seen:
            psz, plead, _, _ = resolve(parent, seen + (sid,))
            size = size if size is not None else psz
            lead = lead if lead is not None else plead
        return size, lead, bef, aft

    out = {}
    for sid in raw:
        size, lead, bef, aft = resolve(sid)
        size = size or 10.0
        out[sid] = (size, lead or size * 1.2, bef, aft)
    return out


def estimate_pages(z, doc):
    """Lay the text out with real Times New Roman metrics.

    Word's justification and hyphenation are not reproduced here, so treat this
    as +/- half a page -- but it is measured rather than guessed, and it is the
    number that decides whether the paper still fits EACE's 10-page limit.
    """
    from PIL import ImageFont
    width_pt, height_pt = page_box(doc)
    metrics = style_metrics(z.read('word/styles.xml'))
    metrics.setdefault('Normal', (10.0, 12.0, 0.0, 0.0))

    cache = {}

    def wrapped(text, size):
        if size not in cache:
            # measure at 4x then scale, so sub-point widths survive rounding
            cache[size] = ImageFont.truetype(
                r'C:\Windows\Fonts\times.ttf', int(round(size * 4)))
        font = cache[size]
        scale = size / int(round(size * 4))
        lines, cur = 1, 0.0
        space = font.getlength(' ') * scale
        for word in text.split():
            w = font.getlength(word) * scale
            if cur and cur + space + w > width_pt:
                lines += 1
                cur = w
            else:
                cur += (space if cur else 0) + w
        return lines

    # Walk the body's DIRECT children only. doc.iter() would also return the
    # paragraphs inside every table cell, which are already accounted for by
    # the row height below -- counting both put the estimate 3 pages long.
    total = 0.0
    for el in doc.find(W + 'body'):
        if el.tag == W + 'p':
            st = el.find('./' + W + 'pPr/' + W + 'pStyle')
            st = st.get(W + 'val') if st is not None else 'Normal'
            txt = ''.join(t.text or '' for t in el.iter(W + 't'))
            size, lead, bef, aft = metrics.get(st, metrics['Normal'])
            total += bef + aft + (2 if st == 'equation'
                                  else wrapped(txt, size)) * lead
            for d in el.iter(W + 'drawing'):
                ext = d.find('.//{http://schemas.openxmlformats.org/drawingml'
                             '/2006/wordprocessingDrawing}extent')
                if ext is not None:
                    total += int(ext.get('cy')) / 12700.0   # EMU -> pt
        elif el.tag == W + 'tbl':
            rows = len(list(el.iter(W + 'tr')))
            total += rows * 11.5 + 6      # 9 pt cells, one line each
    return total / height_pt, total


def fail(problems, msg):
    problems.append(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('docx', nargs='?', default='paper/Kumar_CC-ResDiff.docx')
    args = ap.parse_args()

    problems = []
    z = zipfile.ZipFile(args.docx)
    names = set(z.namelist())

    # ---- 1. every xml part parses -------------------------------------
    for n in sorted(names):
        if n.endswith('.xml') or n.endswith('.rels'):
            try:
                ET.fromstring(z.read(n))
            except ET.ParseError as e:
                fail(problems, 'malformed XML in %s: %s' % (n, e))
    if problems:
        print('\n'.join(problems))
        return 1

    doc = ET.fromstring(z.read('word/document.xml'))
    rels = ET.fromstring(z.read('word/_rels/document.xml.rels'))
    relmap = {r.get('Id'): r.get('Target') for r in rels}

    # ---- 2. relationships resolve -------------------------------------
    used = set()
    for el in doc.iter():
        for k, v in el.attrib.items():
            if k.startswith(R):
                used.add(v)
    for rid in sorted(used):
        if rid not in relmap:
            fail(problems, 'document references missing relationship %s' % rid)
        else:
            tgt = relmap[rid]
            if not tgt.startswith(('http', 'file:')) and \
                    'word/' + tgt.lstrip('/') not in names:
                fail(problems, 'relationship %s -> %s, part not in package'
                     % (rid, tgt))
    for r in rels:
        t = r.get('Target')
        if r.get('TargetMode') != 'External' and \
                'word/' + t.lstrip('/') not in names:
            fail(problems, 'dangling relationship %s -> %s' % (r.get('Id'), t))

    # ---- 3. styles exist ----------------------------------------------
    styles = ET.fromstring(z.read('word/styles.xml'))
    known = {s.get(W + 'styleId') for s in styles.iter(W + 'style')}
    for el in doc.iter():
        if el.tag in (W + 'pStyle', W + 'rStyle'):
            v = el.get(W + 'val')
            if v not in known:
                fail(problems, 'unknown style %r' % v)

    # ---- 4. content ----------------------------------------------------
    paras = []
    for p in doc.iter(W + 'p'):
        st = p.find('./' + W + 'pPr/' + W + 'pStyle')
        txt = ''.join(t.text or '' for t in p.iter(W + 't'))
        math = ''.join(t.text or '' for t in p.iter(M + 't'))
        paras.append((st.get(W + 'val') if st is not None else 'Normal',
                      txt, math))

    order = [s for s, _, _ in paras]
    for want in ('papertitle', 'author', 'address', 'abstract', 'keywords'):
        if want not in order:
            fail(problems, 'missing %s paragraph' % want)
    if order[:1] != ['papertitle']:
        fail(problems, 'document does not start with papertitle (starts %r)'
             % order[:1])

    body_text = '\n'.join(t for _, t, _ in paras)
    for pat, what in ((r'\\[A-Za-z]+', 'LaTeX macro'),
                      (r'(?<!\w)\$', 'math delimiter $'),
                      (r'\{|\}', 'brace'),
                      (r'\?\?', 'unresolved cross-reference')):
        for hit in set(re.findall(pat, body_text)):
            ctx = body_text[max(0, body_text.find(hit) - 50):
                            body_text.find(hit) + 50].replace('\n', ' ')
            fail(problems, '%s %r survived conversion: ...%s...'
                 % (what, hit, ctx))

    tbls = list(doc.iter(W + 'tbl'))
    figs = list(doc.iter(W + 'drawing'))
    eqs = [p for p in paras if p[0] == 'equation']
    refs = [p for p in paras if p[0] == 'referenceitem']

    # ---- 5. page estimate ---------------------------------------------
    pages, height = estimate_pages(z, doc)

    print('%s  (%.0f KB)' % (args.docx, os.path.getsize(args.docx) / 1024))
    print('  paragraphs %d | tables %d | figures %d | equations %d | refs %d'
          % (len(paras), len(tbls), len(figs), len(eqs), len(refs)))
    print('  styles used: %s'
          % ', '.join(sorted({s for s, _, _ in paras})))
    print('  headings:')
    for s, t, _ in paras:
        if s in ('heading1', 'heading2'):
            print('     %s  %s' % ('  ' if s == 'heading2' else '', t))
    w, h = page_box(doc)
    print('  text block %.0f x %.0f pt; content %.0f pt' % (w, h, height))
    print('  estimated length: ~%.1f pages at the template\'s own spacing '
          '(EACE limit 10)' % pages)
    if pages > 10:
        print('  OVER THE LIMIT by ~%.1f pages -- see SUBMISSION_CHECKLIST.md '
              'for the cut order' % (pages - 10))
    print('  equations carry OMML: %s'
          % ('yes' if any(m for _, _, m in eqs) else 'NO -- math is missing'))

    if problems:
        print('\nPROBLEMS (%d):' % len(problems))
        for p in problems:
            print('  - %s' % p)
        return 1
    print('\nOK: no structural problems found.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
