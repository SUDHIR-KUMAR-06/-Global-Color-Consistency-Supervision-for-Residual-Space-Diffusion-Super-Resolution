"""Structural sanity checks for the paper source.

Not a LaTeX compiler -- it catches the classes of damage that actually happen
when the file is edited programmatically: unbalanced environments, dangling
refs/cites, tabular rows that lost a backslash, and stray non-ASCII.
"""
import re
import sys
from collections import Counter

B = chr(92)
path = sys.argv[1] if len(sys.argv) > 1 else 'paper/cc_resdiff.tex'
s = open(path, encoding='utf-8').read()

print('lines           :', s.count('\n'))
print('sections        :', s.count(B + 'section{'))
print('subsections     :', s.count(B + 'subsection{'))
print('tables          :', s.count(B + 'begin{table}'))
print('figures         :', s.count(B + 'begin{figure}'))
print('PENDING uses    :', s.count(B + 'pending{'))

b = Counter(re.findall(B * 2 + r'begin\{(\w+\*?)\}', s))
e = Counter(re.findall(B * 2 + r'end\{(\w+\*?)\}', s))
print('unbalanced envs :', {k: (b[k], e[k]) for k in set(b) | set(e) if b[k] != e[k]} or 'none')

lab = set(re.findall(B * 2 + r'label\{([^}]+)\}', s))
ref = set(re.findall(B * 2 + r'ref\{([^}]+)\}', s))
print('undefined refs  :', (ref - lab) or 'none')
print('unused labels   :', (lab - ref) or 'none')

# a single \cite may carry several comma-separated keys
cit = {k.strip() for grp in re.findall(B * 2 + r'cite\{([^}]+)\}', s) for k in grp.split(',')}
bib = set(re.findall(B * 2 + r'bibitem\{([^}]+)\}', s))
print('undefined cites :', (cit - bib) or 'none')
print('uncited entries :', (bib - cit) or 'none')

print('non-ascii chars :', sorted({c for c in s if ord(c) > 127}) or 'none')

bad = [i + 1 for i, l in enumerate(s.split('\n'))
       if (' & ' in l or 'multicolumn' in l)
       and l.rstrip().endswith(B) and not l.rstrip().endswith(B + B)]
print('bad row endings :', bad or 'none')

# Tabs are NOT benign here: a heredoc eating the backslash of a command
# such as 	imes leaves a literal tab followed by "imes", which renders as
# garbage and is easy to miss by eye.
ctrl = [i + 1 for i, l in enumerate(s.split(chr(10))) if any(ord(c) < 32 for c in l)]
print('control chars   :', ctrl or 'none')

STUBS = ['imes', 'ambda', 'lpha', 'psilon', 'qrt', 'rightarrow']
FULL  = ['times', 'lambda', 'alpha', 'epsilon', 'sqrt', 'rightarrow']
mangled = []
for i2, l in enumerate(s.split(chr(10))):
    for stub, full in zip(STUBS, FULL):
        for m in re.finditer(re.escape(stub), l):
            prev = l[m.start() - 1] if m.start() else ' '
            # a genuine command reads 	imes; a mangled one lost its backslash,
            # leaving the stub preceded by whitespace or a tab. "Timestep" is
            # preceded by a letter and is not a defect.
            if not prev.isalpha() and prev != B:
                mangled.append((i2 + 1, stub))
print('possibly mangled:', mangled or 'none')
