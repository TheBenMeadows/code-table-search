#!/usr/bin/env python3
"""Turn work-unit rows into one BUDA batch file for the science app "codetable".

usage: gen_batch.py UNITS.tsv GROUPS_ROOT CAP_S REPLICAS OUTDIR [--rows FROM-TO]
UNITS.tsv: columns cell alph d target bar fam class order sig maxv groupfile (pilot/pilot_units.tsv);
GROUPS_ROOT is the directory that the groupfile paths are relative to (pilot/units for the pilot).
Each unit becomes REPLICAS jobs (separate BUDA jobs on, usually, different volunteer hosts; assimilate.py needs
agreeing replicas before a NONE counts, since BUDA accepts any returned result as valid). Writes
  OUTDIR/batch/<job>/unit.txt   key=value parameters, cap = CAP_S seconds of running time
  OUTDIR/batch/<job>/group.txt  the subgroup's element list, copied unchanged
  OUTDIR/batch.zip              the batch file to upload to the BOINC Central file sandbox
  OUTDIR/jobs.tsv               job name -> unit, read by assimilate.py
Job names: <cell>__<fam>__<class>__r<i>. A group file whose line count differs from the group order is refused.
Python 3.10 or later, standard library only.
"""
import os, shutil, sys, zipfile

COLS = ['cell', 'alph', 'd', 'target', 'bar', 'fam', 'class', 'order', 'sig', 'maxv', 'groupfile']


def main():
    units, groots, cap, reps, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    lo, hi = 0, 10 ** 9
    if '--rows' in sys.argv:
        a, b = sys.argv[sys.argv.index('--rows') + 1].split('-')
        lo, hi = int(a), int(b)
    rows = [l.rstrip('\n').split('\t') for l in open(units) if l.strip() and not l.startswith('#')][lo:hi]
    bdir = os.path.join(out, 'batch')
    if os.path.exists(bdir):
        sys.exit(f'{bdir} exists; use a new OUTDIR')
    os.makedirs(bdir)
    jobs = []
    for r in rows:
        u = dict(zip(COLS, r, strict=False))
        gpath = os.path.join(groots, u['groupfile'])
        nlines = sum(1 for l in open(gpath) if l.strip())
        if nlines != int(u['order']):
            sys.exit(f'{gpath}: {nlines} elements, manifest order {u["order"]}')
        for i in range(1, reps + 1):
            name = f"{u['cell']}__{u['fam']}__{u['class']}__r{i}"
            jd = os.path.join(bdir, name)
            os.makedirs(jd)
            with open(os.path.join(jd, 'unit.txt'), 'w') as f:
                for k in ['cell', 'alph', 'd', 'target', 'bar', 'fam', 'class', 'order', 'sig']:
                    f.write(f'{k}={u[k]}\n')
                f.write(f'cap={cap}\nmaxv={u["maxv"]}\n')
            shutil.copyfile(gpath, os.path.join(jd, 'group.txt'))
            jobs.append([name] + [u[k] for k in COLS[:9]] + [str(cap)])
    with open(os.path.join(out, 'jobs.tsv'), 'w') as f:
        f.write('#job\t' + '\t'.join(COLS[:9]) + '\tcap\n')
        for j in jobs:
            f.write('\t'.join(j) + '\n')
    zpath = os.path.join(out, 'batch.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for j in sorted(os.listdir(bdir)):
            z.writestr(f'{j}/', '')
            for fn in ('unit.txt', 'group.txt'):
                z.write(os.path.join(bdir, j, fn), f'{j}/{fn}')
    print(f'{len(rows)} units x {reps} replicas = {len(jobs)} jobs -> {zpath} ({os.path.getsize(zpath)} bytes)')


if __name__ == '__main__':
    main()
