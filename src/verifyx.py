"""Independent exact check of a mixed-alphabet code: usage python verifyx.py alph d file  (alph e.g. 3x15 or 2x5,3x9).

One word per line (text after '#' ignored). Checks length, per-coordinate alphabet, distinct words, all pairs at
Hamming distance >= d. Prints size and minimum distance; exit 0 iff OK.
"""
import sys
from itertools import combinations
alph, d, path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
qs = []
for b in alph.split(','):
    a, c = b.split('x'); qs += [int(a)] * int(c)
n = len(qs)
words = [l.split('#', 1)[0].strip() for l in open(path)]
words = [w for w in words if w]
assert all(len(w) == n for w in words), 'wrong length'
assert all(w[i].isdigit() and int(w[i]) < qs[i] for w in words for i in range(n)), 'symbol outside alphabet'
assert len(set(words)) == len(words), 'repeated word'
md = min(sum(a != b for a, b in zip(x, y)) for x, y in combinations(words, 2))
print(f'{path}: {len(words)} words, alph {alph}, min distance {md}, {"OK" if md >= d else "FAIL"} for d={d}')
sys.exit(0 if md >= d else 1)
