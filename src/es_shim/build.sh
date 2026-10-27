#!/bin/sh
# Builds es_shim.so (32-bit) in the manylinux2014_i686 image (glibc 2.17), so the result loads on any
# Linux distribution able to run Counter-Strike: Source. Requires Docker.
#   ./build.sh            -> ../../cstrike/addons/es_shim.so
#   ./build.sh -DES_SHIM_EFENCE   -> diagnostic build (see the comments in es_shim.c)
set -e
cd "$(dirname "$0")"
docker run --rm -v "$PWD:/src" -v "$PWD/../../cstrike/addons:/out" quay.io/pypa/manylinux2014_i686 \
  gcc -m32 -O2 -Wall -Werror -shared -fPIC -fvisibility=hidden -mstackrealign "$@" \
      -o /out/es_shim.so /src/es_shim.c -ldl
echo "built: cstrike/addons/es_shim.so"
