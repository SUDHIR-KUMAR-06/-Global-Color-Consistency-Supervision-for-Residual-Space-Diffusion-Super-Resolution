"""
Convert paper/cc_resdiff_eace.tex into Springer's LNEE Word template.

EACE-2026 accepts Word only, and the Springer template carries the styles the
proceedings are typeset from, so the LaTeX file is the content source and this
script moves it into splnproc1703.docm's styles:

    papertitle / author / address / abstract / keywords
    heading1, heading2      -- auto-numbered by the template; never type numbers
    "heading 3"             -- unnumbered bold run-in headings (\\paragraph)
    equation                -- real OMML, tab-centred, numbered by a SEQ field
    tablecaption            -- above the table;  figurecaption -- below the figure
    referenceitem           -- also auto-numbered

This is a converter for THIS paper, not a general LaTeX engine. Every macro it
meets must be in one of the tables below; anything else raises. A paper that
quietly loses a clause in conversion is worse than one that fails to convert.

Macros are deliberately NOT handled by regex substitution on the source. The
"\\times -> TAB+imes" class of corruption that bit this project repeatedly comes
from exactly that, so the source is tokenised once and emitted as typed runs.

Usage:
    python tools/tex2docx.py
    python tools/tex2docx.py --tex paper/cc_resdiff_eace.tex --out paper/Kumar_CC-ResDiff.docx
"""
import argparse
import os
import re
import zipfile
from xml.sax.saxutils import escape as _esc


def xesc(s):
    """Escape for element content."""
    return _esc(s)


def aesc(s):
    """Escape for an attribute value -- quotes included, which saxutils'
    escape() leaves alone. A SEQ field instruction contains them."""
    return _esc(s, {'"': '&quot;', "'": '&apos;'})

# --------------------------------------------------------------------------
# unit conversions
# --------------------------------------------------------------------------
EMU_PER_CM = 360000
TEXT_WIDTH_CM = 12.2          # Springer text block; matches the template sectPr
TABLE_WIDTH_DXA = 6889        # what the template's own sample table uses

# --------------------------------------------------------------------------
# symbol tables
# --------------------------------------------------------------------------
SYMBOL = {
    'times': '\u00d7', 'to': '\u2192', 'pm': '\u00b1', 'Delta': '\u0394',
    'lambda': '\u03bb', 'epsilon': '\u03b5', 'theta': '\u03b8',
    'alpha': '\u03b1', 'sigma': '\u03c3', 'mu': '\u03bc',
    'sim': '~', 'in': '\u2208', 'downarrow': '\u2193', 'uparrow': '\u2191',
    'cdot': '\u00b7', 'ldots': '\u2026', 'dots': '\u2026',
    'leq': '\u2264', 'geq': '\u2265', 'approx': '\u2248', 'neq': '\u2260',
    'infty': '\u221e',
}
# Binary operators and relations. TeX spaces these out from their operands
# regardless of how the author typed it, and leaves ordinary symbols tight --
# which is why "$k \times k$" is "k x k" but "$\Delta c$" is one token.
# A trailing operator with nothing to its right (the "$8\times$" idiom, meaning
# eightfold) is an ordinary symbol, so it stays tight.
BINARY = {'\u00d7', '\u00b1', '\u2192', '\u2208', '\u00b7', '\u2264',
          '\u2265', '\u2248', '\u2260'}
THIN = '\u2009'
# spacing macros -> what they become in Word
SPACING = {'quad': '\u2003', 'qquad': '\u2003\u2003'}
# macros that carry no content of their own at inline level
INLINE_IGNORE = {'big', 'Big', 'bigg', 'Bigg', 'left', 'right', 'displaystyle',
                 'small', 'normalsize', 'centering', 'noindent', 'protect'}
ESCAPES = {'%': '%', '&': '&', '_': '_', '#': '#', '{': '{', '}': '}',
           '$': '$', '|': '\u2016', ' ': ' ', ',': '\u2009', ';': '\u2009',
           ':': '\u2009', '!': ''}
ACCENTS = {"'": {'e': '\u00e9', 'a': '\u00e1', 'o': '\u00f3', 'i': '\u00ed',
                 'u': '\u00fa', 'c': '\u0107', 's': '\u015b', 'n': '\u0144'}}


# ==========================================================================
# inline renderer:  LaTeX fragment -> list of formatted runs
# ==========================================================================
# Characters Times New Roman does not contain. Word would silently substitute
# some other font for these, which is exactly the failure the Springer
# instructions warn about ("special characters ... can cause these characters to
# disappear"), so name the substitute ourselves. tools/check_docx.py verifies
# the coverage, so anything new shows up as a failure rather than as a box.
FALLBACK_FONT = {'∈': 'Cambria Math'}      # element-of


class Run:
    __slots__ = ('t', 'i', 'b', 'sub', 'sup', 'tt', 'style', 'font')

    def __init__(self, t, i=False, b=False, sub=False, sup=False, tt=False,
                 style=None, font=None):
        self.t, self.i, self.b = t, i, b
        self.sub, self.sup, self.tt, self.style = sub, sup, tt, style
        self.font = font

    def key(self):
        return (self.i, self.b, self.sub, self.sup, self.tt, self.style,
                self.font)


class Inline:
    """Tokenises a LaTeX fragment into runs. Raises on unknown macros."""

    def __init__(self, refs, cites):
        self.refs = refs          # label -> printed number
        self.cites = cites        # bib key -> printed number
        self.unknown = set()

    def render(self, text):
        self.out = []
        self.s, self.i = text, 0
        self._parse({}, None)
        if self.unknown:
            raise SystemExit(
                'tex2docx: unhandled macros %s\n'
                'Add them to SYMBOL/INLINE_IGNORE or to Inline._macro, then '
                're-run. Nothing was written.' % sorted(self.unknown))
        return self._merge()

    # -- emitting ----------------------------------------------------------
    def _emit(self, text, st):
        for ch in text:
            italic = st.get('i', False)
            if (st.get('math') and not st.get('upright')
                    and ch.isascii() and ch.isalpha()):
                italic = True
            self.out.append(Run(ch, italic, st.get('b', False),
                                st.get('sub', False), st.get('sup', False),
                                st.get('tt', False), st.get('style'),
                                FALLBACK_FONT.get(ch)))

    def _merge(self):
        merged = []
        for r in self.out:
            if merged and merged[-1].key() == r.key():
                merged[-1].t += r.t
            else:
                merged.append(r)
        return [r for r in merged if r.t]

    # -- reading -----------------------------------------------------------
    def _group(self):
        """Read a balanced {...} (or one token) and return its raw source."""
        s = self.s
        while self.i < len(s) and s[self.i] in ' \n':
            self.i += 1
        if self.i >= len(s):
            return ''
        if s[self.i] != '{':
            m = re.match(r'\\[A-Za-z]+|.', s[self.i:], re.S)
            self.i += m.end()
            return m.group(0)
        depth, j = 0, self.i
        while j < len(s):
            if s[j] == '{':
                depth += 1
            elif s[j] == '}':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        raw = s[self.i + 1:j]
        self.i = j + 1
        return raw

    def _right_operand(self):
        """Is there an atom to the right, inside this math group? '$8\\times$'
        has none, so its operator is a suffix rather than a binary op."""
        j = self.i
        while j < len(self.s) and self.s[j] in ' \n':
            j += 1
        return j < len(self.s) and self.s[j] not in '$}'

    def _sub_parse(self, raw, st):
        s0, i0 = self.s, self.i
        self.s, self.i = raw, 0
        self._parse(st, None)
        self.s, self.i = s0, i0

    # -- main loop ---------------------------------------------------------
    def _parse(self, st, stop):
        s = self.s
        while self.i < len(s):
            c = s[self.i]
            if stop is not None and c == stop:
                self.i += 1
                return
            if c == '{':
                self.i += 1
                self._parse(dict(st), '}')
            elif c == '}':
                self.i += 1
                return
            elif c == '$':
                self.i += 1
                self._parse(dict(st, math=True), '$')
            elif c == '\\':
                self._backslash(st)
            elif c in '_^' and st.get('math'):
                self.i += 1
                key = 'sub' if c == '_' else 'sup'
                nst = dict(st)
                nst[key] = True
                nst['sub' if key == 'sup' else 'sup'] = False
                self._sub_parse(self._group(), nst)
            elif c == '%':
                nl = s.find('\n', self.i)
                self.i = len(s) if nl < 0 else nl + 1
            elif s.startswith('---', self.i):
                self._emit('\u2014', st)
                self.i += 3
            elif s.startswith('--', self.i):
                self._emit('\u2013', st)
                self.i += 2
            elif s.startswith('``', self.i):
                self._emit('\u201c', st)
                self.i += 2
            elif s.startswith("''", self.i):
                self._emit('\u201d', st)
                self.i += 2
            elif c == '~':
                self._emit('\u00a0', st)
                self.i += 1
            elif c == '-' and st.get('math'):
                self._emit('\u2212', st)
                self.i += 1
            elif c == '\n':
                self._emit(' ', st)
                self.i += 1
            else:
                self._emit(c, st)
                self.i += 1

    def _backslash(self, st):
        s = self.s
        m = re.match(r'\\([A-Za-z]+)', s[self.i:])
        if not m:
            ch = s[self.i + 1] if self.i + 1 < len(s) else ''
            self.i += 2
            if ch in ACCENTS:
                letter = s[self.i]
                self.i += 1
                self._emit(ACCENTS[ch].get(letter, letter), st)
            elif ch in ESCAPES:
                self._emit(ESCAPES[ch], st)
            elif ch == '\\':
                # A line break inside a heading or title is a word gap here.
                # Swallow the newline that follows it, or you get two spaces.
                self._emit(' ', st)
                while self.i < len(s) and s[self.i] in ' \n':
                    self.i += 1
            else:
                self.unknown.add('\\' + ch)
            return
        name = m.group(1)
        self.i += m.end()
        # TeX swallows whitespace after a control word, so "$\Delta c$" is
        # "Delta-c", not "Delta space c". Without this you get stray spaces in
        # every symbol macro and a double space after every {\em ...}.
        while self.i < len(s) and s[self.i] in ' \n':
            self.i += 1
        self._macro(name, st)

    def _macro(self, name, st):
        if name in INLINE_IGNORE:
            return
        if name in SYMBOL:
            sym = SYMBOL[name]
            if st.get('math') and sym in BINARY and self._right_operand():
                # Normalise whatever the author typed to one thin space a side.
                while self.out and self.out[-1].t.endswith((' ', ' ')):
                    self.out[-1].t = self.out[-1].t[:-1]
                    if not self.out[-1].t:
                        self.out.pop()
                self._emit(THIN + sym + THIN, dict(st, upright=True))
            else:
                self._emit(sym, dict(st, upright=True))
            return
        if name in SPACING:
            self._emit(SPACING[name], st)
            return
        if name in ('emph', 'textit', 'mathit'):
            self._sub_parse(self._group(), dict(st, i=not st.get('i', False)))
        elif name in ('textbf', 'best'):
            self._sub_parse(self._group(), dict(st, b=True))
        elif name == 'texttt':
            self._sub_parse(self._group(), dict(st, tt=True))
        elif name in ('text', 'mathrm', 'textrm', 'mbox'):
            self._sub_parse(self._group(), dict(st, upright=True))
        elif name in ('mathcal', 'mathbb', 'mathbf', 'mathsf'):
            self._sub_parse(self._group(), dict(st, math=True))
        elif name == 'em':
            st['i'] = True
        elif name == 'bf':
            st['b'] = True
        elif name == 'sqrt':
            raw = self._group()
            self._emit('\u221a', dict(st, upright=True))
            compound = bool(re.search(r'[-+\s]', raw.strip()))
            if compound:
                self._emit('(', dict(st, upright=True))
            self._sub_parse(raw, st)
            if compound:
                self._emit(')', dict(st, upright=True))
        elif name == 'frac':
            num, den = self._group(), self._group()
            self._emit('(', dict(st, upright=True))
            self._sub_parse(num, st)
            self._emit(')/(', dict(st, upright=True))
            self._sub_parse(den, st)
            self._emit(')', dict(st, upright=True))
        elif name == 'bar':
            raw = self._group().strip()
            if raw == r'\alpha':
                self._emit('\u1fb1', dict(st, upright=True))   # precomposed
            else:
                self._sub_parse(raw, st)
                self._emit('\u0305', st)
        elif name == 'hat':
            self._sub_parse(self._group(), st)
            self._emit('\u0302', st)
        elif name == 'cite':
            keys = [k.strip() for k in self._group().split(',')]
            missing = [k for k in keys if k not in self.cites]
            if missing:
                raise SystemExit('tex2docx: \\cite to unknown key(s) %s' % missing)
            self._emit('[%s]' % ', '.join(str(self.cites[k]) for k in keys),
                       dict(st, math=False, upright=True))
        elif name == 'ref':
            key = self._group().strip()
            if key not in self.refs:
                raise SystemExit('tex2docx: \\ref to unknown label %r' % key)
            self._emit(self.refs[key], dict(st, math=False, upright=True))
        elif name == 'label':
            self._group()
        else:
            self.unknown.add('\\' + name)


# ==========================================================================
# OMML:  real Word equations for the four numbered displays
# ==========================================================================
MFONT = '<w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/></w:rPr>'


def mr(t):
    """Math run -- italic, which is OMML's default for variables."""
    return '<m:r>%s<m:t xml:space="preserve">%s</m:t></m:r>' % (MFONT, xesc(t))


def mup(t):
    """Upright math run: operators, digits, multi-letter names."""
    return ('<m:r><m:rPr><m:sty m:val="p"/></m:rPr>%s'
            '<m:t xml:space="preserve">%s</m:t></m:r>' % (MFONT, xesc(t)))


def msub(e, s):
    return '<m:sSub><m:e>%s</m:e><m:sub>%s</m:sub></m:sSub>' % (e, s)


def msubsup(e, sb, sp):
    return ('<m:sSubSup><m:e>%s</m:e><m:sub>%s</m:sub><m:sup>%s</m:sup>'
            '</m:sSubSup>' % (e, sb, sp))


def mfrac(n, d):
    return '<m:f><m:num>%s</m:num><m:den>%s</m:den></m:f>' % (n, d)


def mrad(e):
    return ('<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/>'
            '<m:e>%s</m:e></m:rad>' % e)


def mdel(e, beg='(', end=')'):
    return ('<m:d><m:dPr><m:begChr m:val="%s"/><m:endChr m:val="%s"/></m:dPr>'
            '<m:e>%s</m:e></m:d>' % (aesc(beg), aesc(end), e))


def macc(e, ch):
    return ('<m:acc><m:accPr><m:chr m:val="%s"/></m:accPr><m:e>%s</m:e>'
            '</m:acc>' % (aesc(ch), e))


def _args():
    """(r_t, t, c) -- the conditioning argument list, used three times."""
    return mdel(msub(mr('r'), mr('t')) + mup(', ') + mr('t') + mup(', ') + mr('c'))


def _alpha_bar_t():
    return msub(macc(mr('\u03b1'), '\u0305'), mr('t'))


def build_equations():
    """OMML for each labelled display. Hand-built so each is auditable."""
    eps_theta = msub(mr('\u03b5'), mr('\u03b8'))

    ddpm_norm = msub(mdel(mr('\u03b5') + mup(' \u2212 ') + eps_theta + _args(),
                          '\u2016', '\u2016'), mup('1'))
    ddpm = (msub(mr('L'), mup('DDPM')) + mup(' = ') + mr('E')
            + mdel(ddpm_norm, '[', ']'))

    num = (msub(mr('r'), mr('t')) + mup(' \u2212 ')
           + mrad(mup('1 \u2212 ') + _alpha_bar_t()) + eps_theta + _args())
    x0 = (msub(macc(mr('r'), '\u0302'), mup('0')) + mup(' = ')
          + mfrac(num, mrad(_alpha_bar_t())))

    pooled = (msub(mr('P'), mr('k'))
              + mdel(msub(macc(mr('x'), '\u0302'), mr('HR')))
              + mup(' \u2212 ') + msub(mr('P'), mr('k'))
              + mdel(msub(mr('x'), mr('HR'))))
    gcc = (msub(mr('L'), mup('GCC')) + mup(' = ')
           + msubsup(mdel(pooled, '\u2016', '\u2016'), mup('2'), mup('2')))

    total = (mr('L') + mup(' = ') + msub(mr('L'), mup('DDPM')) + mup(' + ')
             + mr('\u03bb') + msub(mr('L'), mup('GCC')))

    return {'eq:ddpm': ddpm, 'eq:x0': x0, 'eq:gcc': gcc, 'eq:total': total}


# ==========================================================================
# WordprocessingML emitters
# ==========================================================================
def runs_xml(runs, unbold=False):
    """unbold: stamp an explicit b=0 on every non-bold run. The template's
    'heading 3' paragraph style carries a stray <w:b/> inside its <w:pPr>, which
    is not schema-valid there and which Word should ignore -- but the template's
    own macro defensively un-bolds the body text of a run-in heading, so do the
    same rather than bet on how a Word version we cannot test parses it."""
    out = []
    for r in runs:
        rpr = []
        if r.style:
            rpr.append('<w:rStyle w:val="%s"/>' % r.style)
        if r.tt:
            rpr.append('<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/>')
        elif r.font:
            rpr.append('<w:rFonts w:ascii="%s" w:hAnsi="%s"/>' % (r.font, r.font))
        if r.b:
            rpr.append('<w:b/>')
        elif unbold:
            rpr.append('<w:b w:val="0"/>')
        if r.i:
            rpr.append('<w:i/>')
        if r.sub:
            rpr.append('<w:vertAlign w:val="subscript"/>')
        if r.sup:
            rpr.append('<w:vertAlign w:val="superscript"/>')
        pr = '<w:rPr>%s</w:rPr>' % ''.join(rpr) if rpr else ''
        out.append('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>'
                   % (pr, xesc(r.t)))
    return ''.join(out)


def para(style, body, extra_ppr=''):
    ppr = '<w:pPr><w:pStyle w:val="%s"/>%s</w:pPr>' % (style, extra_ppr)
    return '<w:p>%s%s</w:p>' % (ppr, body)


def counter(number, bold):
    """Caption and equation numbers, as literal text rather than a SEQ field.

    The Springer macro uses SEQ fields so Word renumbers when you move things
    around. We do not need that: the .tex is the source of truth and every
    number here is recomputed from it on each build. Meanwhile the fields
    actively hurt -- LibreOffice re-evaluates SEQ on load and resets every one
    to 1, so a PDF exported from a field version reads "Table 1" five times and
    "(1)" four times. Literal numbers render correctly in every viewer.

    The consequence to know about: reordering tables *inside Word* will not
    renumber them. Reorder in the .tex and re-run this script instead.
    """
    return ('<w:r>%s<w:t>%d</w:t></w:r>'
            % ('<w:rPr><w:b/></w:rPr>' if bold else '', number))


CAPTION_PT = 9.0              # tablecaption / figurecaption are sz 18


def line_count(text, size_pt, width_pt=TEXT_WIDTH_CM * 72 / 2.54):
    """How many lines this text takes at `size_pt` across the text block."""
    try:
        from PIL import ImageFont
        font = ImageFont.truetype(r'C:\Windows\Fonts\times.ttf',
                                  int(round(size_pt * 4)))
        scale = size_pt / int(round(size_pt * 4))
        width = lambda s: font.getlength(s) * scale          # noqa: E731
    except Exception:                                        # no font? estimate
        width = lambda s: len(s) * size_pt * 0.46            # noqa: E731
    lines, cur, space = 1, 0.0, width(' ')
    for word in text.split():
        w = width(word)
        if cur and cur + space + w > width_pt:
            lines, cur = lines + 1, w
        else:
            cur += (space if cur else 0) + w
    return lines


def caption_para(style, word, number, runs):
    """'Table 3.' / 'Fig. 1.' in bold, then the caption text.

    The template's caption styles are centred, and its macro switches a caption
    to justified once it runs past one line ("Short captions are centered,
    while long ones are justified"). Six centred lines under a figure look
    wrong, so apply the same rule.
    """
    lead = ('<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">%s </w:t></w:r>'
            % word)
    dot = '<w:r><w:rPr><w:b/></w:rPr><w:t>.</w:t></w:r>'
    gap = '<w:r><w:t xml:space="preserve"> </w:t></w:r>'
    plain = '%s %d. %s' % (word, number, ''.join(r.t for r in runs))
    jc = ('<w:jc w:val="both"/>'
          if line_count(plain, CAPTION_PT) > 1 else '')
    return para(style, lead + counter(number, True) + dot + gap + runs_xml(runs),
                jc)


def equation_para(omml, number):
    """Template layout: tab, equation, tab, (n) -- matching the sample doc."""
    return para('equation',
                '<w:r><w:tab/></w:r><m:oMath>%s</m:oMath>'
                '<w:r><w:tab/><w:t>(</w:t></w:r>%s<w:r><w:t>)</w:t></w:r>'
                % (omml, counter(number, False)))


def table_xml(spec, rows, inline):
    """rows: list of dicts {cells, top, bot}; borders follow booktabs rules."""
    aligns = [c for c in spec if c in 'lcr']
    ncols = len(aligns)

    rendered = []
    for row in rows:
        cells = []
        for cell in row['cells']:
            span, txt = 1, cell
            mc = re.match(r'\s*\\multicolumn\{(\d+)\}\{([lcr])\}\{(.*)\}\s*$',
                          cell, re.S)
            if mc:
                span, txt = int(mc.group(1)), mc.group(3)
            cells.append((span, inline.render(txt)))
        rendered.append(dict(row, cells=cells))

    # column widths proportional to the widest plain text each column holds
    weights = [1.0] * ncols
    for row in rendered:
        col = 0
        for span, runs in row['cells']:
            if span == 1 and col < ncols:
                n = len(''.join(r.t for r in runs))
                weights[col] = max(weights[col], max(n, 4))
            col += span
    total = sum(weights)
    widths = [int(TABLE_WIDTH_DXA * w / total) for w in weights]
    widths[-1] += TABLE_WIDTH_DXA - sum(widths)

    body = []
    for row in rendered:
        tcs, col = [], 0
        for span, runs in row['cells']:
            w = sum(widths[col:col + span])
            borders = []
            if row['top']:
                borders.append('<w:top w:val="single" w:sz="%d" w:space="0" '
                               'w:color="000000"/>' % row['top'])
            if row['bot']:
                borders.append('<w:bottom w:val="single" w:sz="%d" w:space="0" '
                               'w:color="000000"/>' % row['bot'])
            bx = '<w:tcBorders>%s</w:tcBorders>' % ''.join(borders) if borders else ''
            gs = '<w:gridSpan w:val="%d"/>' % span if span > 1 else ''
            jc = {'l': 'left', 'c': 'center', 'r': 'right'}[aligns[min(col, ncols - 1)]]
            ppr = ('<w:pPr><w:ind w:firstLine="0"/><w:jc w:val="%s"/>'
                   '<w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr></w:pPr>'
                   % jc)
            # table body is 9 pt in the template, so stamp w:sz on every run
            inner = runs_xml(runs).replace(
                '<w:rPr>', '<w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/>')
            inner = re.sub(r'(<w:r>)(<w:t)',
                           r'\1<w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/>'
                           r'</w:rPr>\2', inner)
            tcs.append('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s%s</w:tcPr>'
                       '<w:p>%s%s</w:p></w:tc>' % (w, gs, bx, ppr, inner))
            col += span
        body.append('<w:tr><w:trPr><w:jc w:val="center"/></w:trPr>%s</w:tr>'
                    % ''.join(tcs))

    grid = ''.join('<w:gridCol w:w="%d"/>' % w for w in widths)
    return ('<w:tbl><w:tblPr><w:tblW w:w="%d" w:type="dxa"/>'
            '<w:jc w:val="center"/><w:tblLayout w:type="fixed"/>'
            '<w:tblCellMar><w:left w:w="70" w:type="dxa"/>'
            '<w:right w:w="70" w:type="dxa"/></w:tblCellMar>'
            '<w:tblLook w:val="0000"/></w:tblPr>'
            '<w:tblGrid>%s</w:tblGrid>%s</w:tbl>'
            % (TABLE_WIDTH_DXA, grid, ''.join(body)))


def image_para(rid, width_cm, aspect, name):
    cx = int(width_cm * EMU_PER_CM)
    cy = int(cx * aspect)
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    ns_pic = 'http://schemas.openxmlformats.org/drawingml/2006/picture'
    return para('image',
                '<w:r><w:drawing>'
                '<wp:inline distT="0" distB="0" distL="0" distR="0">'
                '<wp:extent cx="%d" cy="%d"/>'
                '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
                '<wp:docPr id="1" name="Picture 1" descr="%s"/>'
                '<wp:cNvGraphicFramePr>'
                '<a:graphicFrameLocks xmlns:a="%s" noChangeAspect="1"/>'
                '</wp:cNvGraphicFramePr>'
                '<a:graphic xmlns:a="%s">'
                '<a:graphicData uri="%s">'
                '<pic:pic xmlns:pic="%s">'
                '<pic:nvPicPr><pic:cNvPr id="0" name="%s"/><pic:cNvPicPr/>'
                '</pic:nvPicPr>'
                '<pic:blipFill><a:blip r:embed="%s"/>'
                '<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
                '<a:ext cx="%d" cy="%d"/></a:xfrm>'
                '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
                '</pic:pic></a:graphicData></a:graphic>'
                '</wp:inline></w:drawing></w:r>'
                % (cx, cy, xesc(name), ns_a, ns_a, ns_pic, ns_pic,
                   xesc(name), rid, cx, cy))


# ==========================================================================
# LaTeX document parsing
# ==========================================================================
def strip_comments(tex):
    out = []
    for line in tex.split('\n'):
        j, esc = None, False
        for k, ch in enumerate(line):
            if ch == '\\':
                esc = not esc
            elif ch == '%' and not esc:
                j = k
                break
            else:
                esc = False
        out.append(line if j is None else line[:j])
    return '\n'.join(out)


def brace_arg(s, start):
    """Read a balanced {...} beginning at s[start] == '{'. Returns (raw, end)."""
    assert s[start] == '{', s[start:start + 40]
    depth, j = 0, start
    while j < len(s):
        if s[j] == '{':
            depth += 1
        elif s[j] == '}':
            depth -= 1
            if depth == 0:
                return s[start + 1:j], j + 1
        j += 1
    raise SystemExit('tex2docx: unbalanced braces near %r' % s[start:start + 60])


def split_cells(row):
    cells, depth, buf = [], 0, ''
    for ch in row:
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        if ch == '&' and depth == 0:
            cells.append(buf)
            buf = ''
        else:
            buf += ch
    cells.append(buf)
    return cells


RULE_SZ = {'toprule': 12, 'midrule': 6, 'bottomrule': 12}


def parse_tabular(body):
    items, buf = [], ''
    for raw in body.split('\n'):
        ln = raw.strip()
        if not ln:
            continue
        rm = re.fullmatch(r'\\(toprule|midrule|bottomrule)', ln)
        if rm and not buf:
            items.append(('rule', rm.group(1)))
            continue
        buf += (' ' if buf else '') + ln
        if buf.rstrip().endswith('\\\\'):
            items.append(('row', buf.rstrip()[:-2]))
            buf = ''
    if buf.strip():
        items.append(('row', buf.strip()))

    rows = []
    pending_top = 0
    for kind, val in items:
        if kind == 'rule':
            if val == 'toprule':
                pending_top = RULE_SZ[val]
            elif rows:
                rows[-1]['bot'] = RULE_SZ[val]
        else:
            rows.append({'cells': split_cells(val), 'top': pending_top, 'bot': 0})
            pending_top = 0
    return rows


class Paper:
    """Splits the .tex into an ordered list of blocks and assigns all numbers."""

    def __init__(self, tex):
        self.tex = strip_comments(tex)
        self.blocks = []
        self.refs = {}
        self.cites = {}
        self._scan_bibliography()
        self._scan_body()

    def _scan_bibliography(self):
        m = re.search(r'\\begin\{thebibliography\}\{[^}]*\}(.*?)'
                      r'\\end\{thebibliography\}', self.tex, re.S)
        if not m:
            raise SystemExit('tex2docx: no thebibliography block found')
        self.bib = []
        for n, bm in enumerate(re.finditer(
                r'\\bibitem\{([^}]*)\}(.*?)(?=\\bibitem\{|\Z)', m.group(1), re.S), 1):
            self.cites[bm.group(1)] = n
            self.bib.append(bm.group(2).strip())

    def _scan_body(self):
        body = self.tex.split(r'\section{Introduction}', 1)
        if len(body) != 2:
            raise SystemExit('tex2docx: could not find \\section{Introduction}')
        body = r'\section{Introduction}' + body[1]
        body = body.split(r'\begin{thebibliography}', 1)[0]

        sec = sub = tab = fig = eq = 0
        i = 0
        while i < len(body):
            m = re.compile(
                r'\\(section|subsection|paragraph)\{|'
                r'\\begin\{(equation|table|figure)\}').search(body, i)
            if not m:
                self._text(body[i:])
                break
            self._text(body[i:m.start()])
            kind = m.group(1) or m.group(2)

            if kind in ('section', 'subsection', 'paragraph'):
                raw, end = brace_arg(body, m.end() - 1)
                i = end
                if kind == 'section':
                    sec += 1
                    sub = 0
                    self.blocks.append(('heading1', raw))
                    self._last_sec = sec
                elif kind == 'subsection':
                    sub += 1
                    self.blocks.append(('heading2', raw))
                    self._pending_label = '%d.%d' % (sec, sub)
                else:
                    self.blocks.append(('runin', raw))
                # a \label on the next line belongs to this heading
                lm = re.match(r'\s*\\label\{([^}]*)\}', body[i:])
                if lm:
                    num = '%d.%d' % (sec, sub) if kind == 'subsection' else str(sec)
                    self.refs[lm.group(1)] = num
                    i += lm.end()
                continue

            env = kind
            em = re.search(r'\\end\{%s\}' % env, body[m.end():])
            if not em:
                raise SystemExit('tex2docx: unterminated %s environment' % env)
            inner = body[m.end():m.end() + em.start()]
            i = m.end() + em.end()

            if env == 'equation':
                eq += 1
                lm = re.search(r'\\label\{([^}]*)\}', inner)
                if not lm:
                    raise SystemExit('tex2docx: unlabelled equation')
                self.refs[lm.group(1)] = str(eq)
                self.blocks.append(('equation', (lm.group(1), eq)))
            elif env == 'table':
                tab += 1
                self.blocks.append(('table', self._table(inner, tab)))
            else:
                fig += 1
                self.blocks.append(('figure', self._figure(inner, fig)))

    def _table(self, inner, number):
        tm = re.search(r'\\begin\{tabular\}\{([^}]*)\}(.*?)\\end\{tabular\}',
                       inner, re.S)
        if not tm:
            raise SystemExit('tex2docx: table without a tabular')
        cm = inner.index(r'\caption{') + len(r'\caption')
        cap, _ = brace_arg(inner, cm)
        lm = re.search(r'\\label\{([^}]*)\}', inner)
        if not lm:
            raise SystemExit('tex2docx: unlabelled table')
        self.refs[lm.group(1)] = str(number)
        return {'spec': tm.group(1), 'rows': parse_tabular(tm.group(2)),
                'caption': cap, 'number': number}

    def _figure(self, inner, number):
        gm = re.search(r'\\includegraphics(?:\[([^\]]*)\])?\{([^}]*)\}', inner)
        if not gm:
            raise SystemExit('tex2docx: figure without \\includegraphics')
        wm = re.search(r'width\s*=\s*([0-9.]+)\\linewidth', gm.group(1) or '')
        cm = inner.index(r'\caption{') + len(r'\caption')
        cap, _ = brace_arg(inner, cm)
        lm = re.search(r'\\label\{([^}]*)\}', inner)
        if not lm:
            raise SystemExit('tex2docx: unlabelled figure')
        self.refs[lm.group(1)] = str(number)
        return {'file': gm.group(2), 'frac': float(wm.group(1)) if wm else 1.0,
                'caption': cap, 'number': number}

    def _text(self, chunk):
        for part in re.split(r'\n\s*\n', chunk):
            if part.strip():
                self.blocks.append(('text', part.strip()))


# ==========================================================================
# package assembly
# ==========================================================================
DROP_PREFIXES = ('customUI/', 'word/vbaProject.bin', 'word/vbaData.xml',
                 'word/_rels/vbaProject.bin.rels', 'word/charts/')


def build(tex_path, template, out_path):
    tex = open(tex_path, encoding='utf-8').read()
    paper = Paper(tex)
    inline = Inline(paper.refs, paper.cites)
    equations = build_equations()

    # ---- header ------------------------------------------------------
    # Work off the comment-stripped source: the preamble carries a long
    # instructions comment that otherwise swallows these matches.
    src = paper.tex

    def macro_arg(name):
        m = re.search(r'\\%s\s*\{' % name, src)
        if not m:
            raise SystemExit('tex2docx: no \\%s{...} in the source' % name)
        return brace_arg(src, m.end() - 1)[0]

    title = macro_arg('title').strip()
    title = re.sub(r'^\\textbf\s*\{(.*)\}$', r'\1', title, flags=re.S).strip()
    out = [para('papertitle', runs_xml(inline.render(title)))]

    names, affils, emails = parse_author_block(macro_arg('author'))
    out.append(para('author', author_runs(names)))
    for n, a in affils:
        out.append(para('address', address_runs(n, a)))
    if emails:
        out.append(para('address', email_runs(emails)))

    abstract = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}',
                         src, re.S).group(1).strip()
    out.append(para('abstract',
                    '<w:r><w:rPr><w:b/></w:rPr>'
                    '<w:t xml:space="preserve">Abstract. </w:t></w:r>'
                    + runs_xml(inline.render(abstract))))

    kw = re.search(r'\\textbf\{Keywords:\}(.*?)\n\s*\n', src, re.S).group(1)
    kw = ' '.join(kw.split()).strip().rstrip('.') + '.'
    out.append(para('keywords',
                    '<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">'
                    'Keywords: </w:t></w:r>' + runs_xml(inline.render(kw))))

    # ---- body --------------------------------------------------------
    media = []
    rels_extra = []
    fresh = True          # next text paragraph is the first of its block
    pending_space = False  # ...and needs 6 pt of air above it
    for kind, val in paper.blocks:
        if kind == 'heading1':
            out.append(para('heading1', runs_xml(inline.render(val))))
            fresh = True
        elif kind == 'heading2':
            out.append(para('heading2', runs_xml(inline.render(val))))
            fresh = True
        elif kind == 'runin':
            out.append(('RUNIN', val))
            fresh = False
        elif kind == 'equation':
            out.append(equation_para(equations[val[0]], val[1]))
            fresh = True
        elif kind == 'table':
            out.append(caption_para('tablecaption', 'Table', val['number'],
                                    inline.render(val['caption'])))
            out.append(table_xml(val['spec'], val['rows'], inline))
            # A table has no space of its own after it, so the next paragraph
            # would start hard against the bottom rule. 6 pt is what the
            # template's own "add vertical space" macro inserts.
            fresh = pending_space = True
        elif kind == 'figure':
            rid = 'rId900'
            src = os.path.join(os.path.dirname(tex_path), val['file'])
            from PIL import Image
            with Image.open(src) as im:
                aspect = im.size[1] / im.size[0]
            media.append((src, 'word/media/' + os.path.basename(val['file'])))
            rels_extra.append(
                '<Relationship Id="%s" Type="http://schemas.openxmlformats.org'
                '/officeDocument/2006/relationships/image" Target="media/%s"/>'
                % (rid, os.path.basename(val['file'])))
            out.append(image_para(rid, TEXT_WIDTH_CM * val['frac'], aspect,
                                  os.path.basename(val['file'])))
            out.append(caption_para('figurecaption', 'Fig.', val['number'],
                                    inline.render(val['caption'])))
            fresh = True
        else:
            gap = '<w:spacing w:before="120"/>' if pending_space else ''
            if out and isinstance(out[-1], tuple) and out[-1][0] == 'RUNIN':
                head = inline.render(out.pop()[1].rstrip())
                for r in head:
                    r.style, r.b = 'heading3', True
                head.append(Run(' ', b=True, style='heading3'))
                out.append(para('heading 3',
                                runs_xml(head)
                                + runs_xml(inline.render(val), unbold=True),
                                gap))
            else:
                out.append(para('p1a' if fresh else 'Normal',
                                runs_xml(inline.render(val)), gap))
            fresh = pending_space = False

    if any(isinstance(p, tuple) for p in out):
        raise SystemExit('tex2docx: a \\paragraph had no text after it')

    # ---- references --------------------------------------------------
    out.append(para('heading1', runs_xml(inline.render('References')),
                    '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="0"/></w:numPr>'))
    for entry in paper.bib:
        out.append(para('referenceitem',
                        runs_xml(inline.render(' '.join(entry.split())))))

    write_package(template, out_path, ''.join(out), media, rels_extra)
    return paper


def parse_author_block(raw):
    """Pull names, ORCIDs, affiliations and e-mails out of the \\author{} block.

    The first line holds the names. Affiliations may be numbered ("$^{1}$Dept,
    ...") when authors differ, or a single unnumbered line when they share one
    institution -- Springer drops the superscripts in that case.
    """
    # Size commands here are for the LaTeX build's benefit only -- the Word
    # styles set their own sizes -- so drop them before reading the content.
    lines = [re.sub(r'\\(?:small|normalsize|large|footnotesize)\s*', '', l).strip()
             for l in re.split(r'\\\\(?:\[[^\]]*\])?', raw) if l.strip()]
    names, affils, emails = [], [], []
    for k, ln in enumerate(lines):
        if r'\texttt' in ln:
            emails += re.findall(r'\\texttt\{([^}]*)\}', ln)
        elif not names and not affils:
            for part in re.split(r'\s+and\s+', ln):
                part = part.strip()
                if not part:
                    continue
                orc = re.search(r'\\orcid\{([^}]*)\}', part)
                part = re.sub(r'\\orcid\{[^}]*\}', '', part).strip()
                num = re.match(r'(.*?)\$\^\{?(\d+)\}?\$\s*$', part)
                names.append((num.group(1).strip() if num else part,
                              num.group(2) if num else None,
                              orc.group(1) if orc else None))
        else:
            m = re.match(r'\$\^\{?(\d+)\}?\$\s*(.*)$', ln)
            affils.append((m.group(1), m.group(2).strip()) if m else (None, ln))
    if not names:
        raise SystemExit('tex2docx: could not read any author name')
    return names, affils, emails


def author_runs(names):
    out = []
    for k, (name, sup, orcid) in enumerate(names):
        if k:
            out.append('<w:r><w:t xml:space="preserve"> and </w:t></w:r>')
        out.append('<w:r><w:t xml:space="preserve">%s</w:t></w:r>' % xesc(name))
        if sup:
            out.append('<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr>'
                       '<w:t>%s</w:t></w:r>' % xesc(sup))
        if orcid:
            if not re.fullmatch(r'\d{4}-\d{4}-\d{4}-\d{3}[\dX]', orcid):
                raise SystemExit('tex2docx: %r is not a well-formed ORCID id '
                                 '(expected 0000-0000-0000-0000)' % orcid)
            out.append('<w:r><w:rPr><w:rStyle w:val="ORCID"/></w:rPr>'
                       '<w:t>[%s]</w:t></w:r>' % xesc(orcid))
    return ''.join(out)


def address_runs(num, text):
    """A shared affiliation carries no superscript numeral."""
    lead = ('<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr>'
            '<w:t>%s</w:t></w:r>' % xesc(num) if num else '')
    return lead + ('<w:r><w:t xml:space="preserve">%s%s</w:t></w:r>'
                   % (' ' if num else '', xesc(text)))


def email_runs(emails):
    out = []
    for k, e in enumerate(emails):
        if k:
            out.append('<w:r><w:t xml:space="preserve">, </w:t></w:r>')
        out.append('<w:r><w:rPr><w:rStyle w:val="e-mail"/></w:rPr>'
                   '<w:t>%s</w:t></w:r>' % xesc(e))
    return ''.join(out)


def write_package(template, out_path, body_xml, media, rels_extra):
    src = zipfile.ZipFile(template)
    doc = src.read('word/document.xml').decode('utf-8')
    head = doc[:doc.index('<w:body>') + len('<w:body>')]
    sectpr = re.search(r'<w:sectPr.*?</w:sectPr>', doc, re.S).group(0)

    for ns, uri in (('wp', 'http://schemas.openxmlformats.org/drawingml/2006/'
                           'wordprocessingDrawing'),
                    ('m', 'http://schemas.openxmlformats.org/officeDocument/'
                          '2006/math')):
        if 'xmlns:%s=' % ns not in head:
            head = head.replace('<w:document ',
                                '<w:document xmlns:%s="%s" ' % (ns, uri), 1)

    new_doc = head + body_xml + sectpr + '</w:body></w:document>'

    rels = src.read('word/_rels/document.xml.rels').decode('utf-8-sig')
    rels = re.sub(r'<Relationship[^>]*vbaProject[^>]*/>', '', rels)
    rels = re.sub(r'<Relationship[^>]*Target="charts/[^"]*"[^>]*/>', '', rels)
    rels = rels.replace('</Relationships>', ''.join(rels_extra) + '</Relationships>')

    ct = src.read('[Content_Types].xml').decode('utf-8-sig')
    ct = ct.replace('application/vnd.ms-word.document.macroEnabled.main+xml',
                    'application/vnd.openxmlformats-officedocument'
                    '.wordprocessingml.document.main+xml')
    ct = re.sub(r'<Default Extension="bin"[^>]*/>', '', ct)
    ct = re.sub(r'<Override PartName="/word/vbaData\.xml"[^>]*/>', '', ct)
    ct = re.sub(r'<Override PartName="/word/charts/[^"]*"[^>]*/>', '', ct)
    ct = ct.replace('ContentType="image/.png"', 'ContentType="image/png"')

    top = src.read('_rels/.rels').decode('utf-8-sig')
    top = re.sub(r'<Relationship[^>]*customUI[^>]*/>', '', top)

    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for item in src.infolist():
            n = item.filename
            if n.startswith(DROP_PREFIXES) or n.endswith('/'):
                continue
            if n == 'word/document.xml':
                z.writestr(n, new_doc)
            elif n == 'word/_rels/document.xml.rels':
                z.writestr(n, rels)
            elif n == '[Content_Types].xml':
                z.writestr(n, ct)
            elif n == '_rels/.rels':
                z.writestr(n, top)
            else:
                z.writestr(item, src.read(n))
        for disk, inside in media:
            z.write(disk, inside)
    src.close()


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument('--tex', default=os.path.join(here, 'paper',
                                                  'cc_resdiff_eace.tex'))
    ap.add_argument('--template',
                    default=os.path.expanduser(
                        r'~\Downloads\Word_Template\splnproc1703.docm'))
    ap.add_argument('--out', default=os.path.join(here, 'paper',
                                                  'Kumar_CC-ResDiff.docx'))
    args = ap.parse_args()

    if not os.path.exists(args.template):
        raise SystemExit('tex2docx: template not found at %s\n'
                         'Pass --template with the path to splnproc1703.docm.'
                         % args.template)
    paper = build(args.tex, args.template, args.out)
    kinds = [k for k, _ in paper.blocks]
    print('Wrote %s' % args.out)
    print('  %d text blocks, %d sections, %d subsections, %d run-in headings'
          % (kinds.count('text'), kinds.count('heading1'),
             kinds.count('heading2'), kinds.count('runin')))
    print('  %d equations, %d tables, %d figures, %d references'
          % (kinds.count('equation'), kinds.count('table'),
             kinds.count('figure'), len(paper.bib)))


if __name__ == '__main__':
    main()
