#!/bin/sh
# Build the two static osg app files from src/osg.c inside a Debian container (no host toolchain needed):
#   boinc/osg_x86_64_1   gcc -O3 -march=x86-64-v2 -static   (x86-64-v2 = SSE4.2 + POPCNT, every x64 CPU since about 2009)
#   boinc/osg_aarch64_1  aarch64-linux-gnu-gcc -O3 -static
# usage: sh boinc/build_osg.sh [outdir]   (run from the repository root; needs docker; outdir defaults to boinc)
set -eu
out=${1:-boinc}
docker run --rm -v "$PWD/src":/src:ro -v "$(cd "$out" && pwd)":/out debian:trixie-slim sh -c '
  apt-get update -qq && apt-get install -y -qq --no-install-recommends gcc libc6-dev gcc-aarch64-linux-gnu libc6-dev-arm64-cross > /dev/null &&
  gcc -O3 -march=x86-64-v2 -static -o /out/osg_x86_64_1 /src/osg.c &&
  aarch64-linux-gnu-gcc -O3 -static -o /out/osg_aarch64_1 /src/osg.c &&
  gcc --version | head -n 1 && aarch64-linux-gnu-gcc --version | head -n 1'
sha256sum "$out"/osg_x86_64_1 "$out"/osg_aarch64_1
