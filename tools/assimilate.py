#!/usr/bin/env python3
"""Read returned BUDA results of the "codetable" app, re-verify every code, append one line per unit to a results TSV.

usage: assimilate.py JOBS.tsv OUTPUTS RESULTS.tsv CODEDIR [--verifier PATH] [--min-agree K]
JOBS.tsv: gen_batch.py's job list. OUTPUTS: the zip downloaded from the batch page, or a directory of its files
(names batch_<id>__job_<job>__file_result.txt). RESULTS.tsv gets the result-line format of README.md
  cell fam g<k> order sig target= bar= tl= secs= status osg-line
and is only appended to; a unit already in it is skipped, so the script can be rerun as more jobs come back.
Rules, per unit (all replicas of one (cell, fam, class, target)):
  - a result whose cell, fam, class, target or bar differ from its job is rejected;
  - WIN, BAR and LOW carry the code words; each is re-checked with src/verifyx.py (length,
    alphabet, distinct words, every pair at distance >= d) and its word count must equal the reported best.
    A code that fails is rejected and reported. The first verified WIN, else BAR, else LOW is recorded; its code is
    kept as CODEDIR/<cell>__<fam>__<class>.txt and a WIN is also appended to WINS.tsv beside RESULTS.tsv;
  - NONE is a negative, and BUDA accepts any returned result as valid, so NONE is recorded only when at least K
    replicas (default 2) returned NONE and no replica returned a verified code;
  - once every replica is back and none of the above holds, the unit is recorded as TIMEOUT, TOO_MANY or KILLED
    (never a negative), and a lone NONE is listed as unconfirmed;
  - a unit with replicas still out and nothing decisive is left for the next run.
"""
import collections, os, re, subprocess, sys, tempfile, zipfile

VERIFIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'verifyx.py')
NAME = re.compile(r'batch_(\d+)__job_(.+)__file_result\.txt$')
NONNEG = ('TIMEOUT', 'TOO_MANY', 'KILLED')


def read_outputs(src):
    out = {}
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as z:
            for n in z.namelist():
                m = NAME.search(os.path.basename(n))
                if m:
                    out[m.group(2)] = z.read(n).decode('utf-8', 'replace')
    else:
        for n in os.listdir(src):
            m = NAME.search(n)
            if m:
                out[m.group(2)] = open(os.path.join(src, n), encoding='utf-8', errors='replace').read()
    return out


def verify(text, alph, d, best, verifier):
    words = [l.strip() for l in text.split('\n#CODE\n', 1)[1].splitlines() if l.strip() and not l.startswith('#')]
    if len(words) != best:
        return False, f'{len(words)} words, reported best {best}', words
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f:
        f.write('\n'.join(words) + '\n')
    p = subprocess.run([sys.executable, verifier, alph, str(d), f.name], capture_output=True, text=True, check=False)
    os.unlink(f.name)
    msg = (p.stdout.strip() or (p.stderr.strip().splitlines() or ['no output'])[-1]).replace(f.name, 'code')
    return p.returncode == 0, msg, words


JOB_COLS = ['job', 'cell', 'alph', 'd', 'target', 'bar', 'fam', 'class', 'order', 'sig', 'cap']


def load_jobs(jobs_tsv):
    jobs, units = {}, collections.OrderedDict()
    for l in open(jobs_tsv):
        if l.startswith('#') or not l.strip():
            continue
        j = dict(zip(JOB_COLS, l.rstrip('\n').split('\t'), strict=False))
        jobs[j['job']] = j
        units.setdefault((j['cell'], j['fam'], j['class'], j['target']), []).append(j['job'])
    return jobs, units


def load_done(res_tsv):
    done = set()
    if os.path.exists(res_tsv):
        for l in open(res_tsv):
            f = l.rstrip('\n').split('\t')
            if len(f) > 5:
                done.add((f[0], f[1], f[2], f[5][7:]))
    return done


def check_result(n, text, j, verifier):
    """One returned file -> (status, result line, code words or None, check message), or None if rejected."""
    f = text.split('\n', 1)[0].split('\t')
    if len(f) < 11 or (f[0], f[1], f[2], f[5], f[6]) != (j['cell'], j['fam'], j['class'],
                                                      f"target={j['target']}", f"bar={j['bar']}"):
        print(f'REJECTED {n}: result line does not match the job')
        return None
    st = f[9]
    if st not in ('WIN', 'BAR', 'LOW'):
        return st, '\t'.join(f), None, ''
    if '\n#CODE\n' not in text:
        print(f'REJECTED {n}: {st} without code words')
        return None
    best = int(re.search(r'best=(-?\d+)', f[10]).group(1))
    ok, msg, words = verify(text, j['alph'], j['d'], best, verifier)
    if not ok:
        print(f'REJECTED {n}: {st} code fails the check: {msg}')
        return None
    return st, '\t'.join(f), words, msg


def decide(key, got, n_replicas, k_agree):
    """Accepted results of one unit -> the result to record, or None to wait for more replicas."""
    sts = collections.Counter(v[0] for v in got.values())
    for want in ('WIN', 'BAR', 'LOW'):
        if sts[want]:
            if sts['NONE']:
                print(f'DISAGREE {key}: verified {want} but {sts["NONE"]} replica(s) returned NONE')
            return next(v for v in got.values() if v[0] == want)
    if sts['NONE'] >= k_agree:
        return next(v for v in got.values() if v[0] == 'NONE')
    if len(got) < n_replicas or not got:
        return None
    if sts['NONE']:
        print(f'UNCONFIRMED {key}: {sts["NONE"]} NONE of {n_replicas} replicas (need {k_agree}); not a negative')
    nn = [v for v in got.values() if v[0] in NONNEG]
    return max(nn, key=lambda v: int(v[1].split('\t')[8][5:])) if nn else None


def keep_code(key, pick, codedir):
    st, line, words, msg = pick
    cp = os.path.join(codedir, f'{key[0]}__{key[1]}__{key[2]}.txt')
    with open(cp, 'w') as fh:
        fh.write(f'# {key[0]} {key[1]} {key[2]} {st}: {msg}\n' + '\n'.join(words) + '\n')
    print(f'{st} {key[0]} {key[1]} {key[2]} verified: {msg}')
    f = line.split('\t')
    return f'{f[0]}\t{f[1]}\t{f[2]}\torder={f[3]}\tsize={len(words)}\t{f[6]}\t{cp}\tboinc' if st == 'WIN' else None


def main():
    jobs_tsv, src, res_tsv, codedir = sys.argv[1:5]
    verifier = sys.argv[sys.argv.index('--verifier') + 1] if '--verifier' in sys.argv else VERIFIER
    k_agree = int(sys.argv[sys.argv.index('--min-agree') + 1]) if '--min-agree' in sys.argv else 2
    os.makedirs(codedir, exist_ok=True)
    jobs, units = load_jobs(jobs_tsv)
    done = load_done(res_tsv)
    outs = read_outputs(src)
    unknown = sorted(set(outs) - set(jobs))
    if unknown:
        print(f'{len(unknown)} returned files match no job in {jobs_tsv}, ignored: {unknown[:5]}')
    tally = collections.Counter()
    new_lines, wins = [], []
    for key, names in units.items():
        if key in done:
            tally['already recorded'] += 1
            continue
        got = {}
        for n in (n for n in names if n in outs):
            r = check_result(n, outs[n], jobs[n], verifier)
            if r is None:
                tally['rejected'] += 1
            else:
                got[n] = r
        pick = decide(key, got, len(names), k_agree)
        if pick is None:
            tally['waiting'] += 1
            continue
        new_lines.append(pick[1])
        tally[pick[0]] += 1
        if pick[2]:
            w = keep_code(key, pick, codedir)
            if w:
                wins.append(w)
    with open(res_tsv, 'a') as fh:
        for l in new_lines:
            fh.write(l + '\n')
    if wins:
        with open(os.path.join(os.path.dirname(os.path.abspath(res_tsv)), 'WINS.tsv'), 'a') as fh:
            for w in wins:
                fh.write(w + '\n')
    print(f'{len(outs)} result files, {len(units)} units: ' + ', '.join(f'{k} {v}' for k, v in sorted(tally.items())))


if __name__ == '__main__':
    main()
