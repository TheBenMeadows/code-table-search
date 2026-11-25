#!/bin/sh
# BUDA main program of the science app "codetable": one work unit = one (cell, subgroup class).
#
# Input files (in the working directory, which the Docker wrapper mounts at /app):
#   unit.txt   key=value lines: cell alph d target bar fam class order sig cap maxv
#   group.txt  every element of the subgroup, in osg's elements-file format
# App files: this script and osg_<arch>_1 (osg.c built static for x86_64 or aarch64).
# Output file: result.txt. Line 1 is one result line (format in README.md)
#   cell fam class order sig target=T bar=B tl=CAP secs=S STATUS osg-line
# with STATUS one of WIN (best > bar), BAR (best = bar), LOW (target <= best < bar), NONE (exhaustive search
# finished, no invariant code of size >= target), TIMEOUT (search cut by the time budget), TOO_MANY (vertex cap),
# KILLED (hard stop). Only NONE is a negative; TIMEOUT, TOO_MANY and KILLED never are. On WIN, BAR or LOW the
# lines after "#CODE" are osg's header line and the code words, one per line.
#
# Time budget: cap seconds of running time per job, counted across container restarts in the file elapsed_s
# (a paused container does not consume budget). osg itself has no checkpoint: after a restart it searches again
# from the start with the remaining budget, so a NONE always comes from one uninterrupted, complete search.
# osg's own limit covers only its clique search, not the orbit and graph building before it; if the whole run goes
# past cap + max(1800, cap/2) seconds, osg is killed and the result is KILLED.
set -u
U=unit.txt
G=group.txt
OUT=result.txt

die() { echo "codetable: $*" >&2; exit 1; }
val() { sed -n "s/^$1=//p" "$U" | head -n 1 | tr -d '\r'; }
isint() { case "$1" in ''|*[!0-9]*) return 1 ;; *) return 0 ;; esac; }

[ -f "$OUT" ] && head -n 1 "$OUT" | grep -q 'target=' && { echo "codetable: result.txt already written"; exit 0; }
[ -f "$U" ] || die "missing $U"
[ -f "$G" ] || die "missing $G"

cell=$(val cell); alph=$(val alph); d=$(val d); target=$(val target); bar=$(val bar)
fam=$(val fam); cls=$(val class); order=$(val order); sig=$(val sig); cap=$(val cap); maxv=$(val maxv)
for v in d target bar order cap maxv; do eval "x=\$$v"; isint "$x" || die "$v is not a non-negative integer: '$x'"; done
[ -n "$cell" ] && [ -n "$fam" ] && [ -n "$cls" ] && [ -n "$sig" ] || die "cell, fam, class and sig are required"
case "$alph" in *[!0-9x,]*|'') die "bad alph '$alph'" ;; esac

arch=$(uname -m)
src=$(ls osg_"$arch"_* 2>/dev/null | head -n 1)
[ -n "$src" ] || die "no osg binary for $arch"
OSG=/tmp/osg.$$
{ cp "$src" "$OSG" && chmod 755 "$OSG"; } 2>/dev/null || { OSG=./osg.run; cp "$src" "$OSG" && chmod 755 "$OSG"; } || die "cannot stage $src"

el=$(cat elapsed_s 2>/dev/null || echo 0)
isint "$el" || el=0
rem=$((cap - el))
grace=$((cap / 2)); [ "$grace" -lt 1800 ] && grace=1800
hard=$((cap + grace))
killed=0
rm -f code.txt osg.stdout osg.stderr

if [ "$rem" -lt 30 ]; then
    line="TIMEOUT best=-1 (time budget used up across container restarts)"
    rc=0
else
    "$OSG" "$alph" "$d" "$G" "$target" "$rem" "$maxv" code.txt > osg.stdout 2> osg.stderr &
    pid=$!
    last=$(date +%s)
    while [ -d /proc/$pid ] && ! grep -q '^State:[[:space:]]*Z' /proc/$pid/status 2>/dev/null; do
        sleep 5
        now=$(date +%s); dt=$((now - last)); last=$now
        # a gap much longer than the sleep means the container was paused: count only running time
        [ "$dt" -gt 15 ] && dt=5
        [ "$dt" -lt 0 ] && dt=0
        el=$((el + dt))
        echo "$el" > elapsed_s.tmp && mv elapsed_s.tmp elapsed_s
        awk -v e="$el" -v c="$cap" 'BEGIN { f = c > 0 ? e / c : 0; if (f > 0.99) f = 0.99; printf "%.4f\n", f }' > fraction_done
        if [ "$el" -ge "$hard" ]; then kill -9 "$pid" 2>/dev/null; killed=1; break; fi
    done
    wait "$pid"; rc=$?
    line=$(tr '\n' ' ' < osg.stdout | sed 's/[[:space:]]*$//')
    [ -n "$line" ] || line=$(tr '\n' ' ' < osg.stderr | sed 's/[[:space:]]*$//')
    [ "$killed" = 1 ] && line="$line KILLED"
fi
rm -f "$OSG"

if [ "$killed" = 0 ] && [ "$rc" != 0 ] && [ "$rc" != 3 ]; then
    cat osg.stderr >&2
    die "osg exited with status $rc"
fi

status=$(printf '%s\n' "$line" | awk -v t="$target" -v b="$bar" '{
    if ($0 ~ /TOO_MANY_VERTICES/) { print "TOO_MANY -1"; exit }
    if ($0 ~ /KILLED/ || $0 !~ /best=/) { print "KILLED -1"; exit }
    s = $0; sub(/.*best=/, "", s); sub(/[^-0-9].*/, "", s); best = s + 0
    if (best > b) st = "WIN"; else if (best == b) st = "BAR"; else if (best >= t) st = "LOW"
    else if ($0 ~ /TIMEOUT/) st = "TIMEOUT"; else st = "NONE"
    print st, best
}')
st=${status% *}
best=${status#* }

printf '%s\t%s\t%s\t%s\t%s\ttarget=%s\tbar=%s\ttl=%s\tsecs=%s\t%s\t%s\n' \
    "$cell" "$fam" "$cls" "$order" "$sig" "$target" "$bar" "$cap" "$el" "$st" "$line" > "$OUT.tmp"
if [ "$best" -ge "$target" ] && [ -s code.txt ]; then
    echo "#CODE" >> "$OUT.tmp"
    cat code.txt >> "$OUT.tmp"
fi
mv "$OUT.tmp" "$OUT"
echo 1 > fraction_done
echo "codetable: $cell $fam $cls $st secs=$el"
exit 0
