#!/usr/bin/env bash
# Prepare an xauth cookie for the GUI containers instead of `xhost +`, which
# opens your X server to anything running on the box.
set -euo pipefail

XAUTH=/tmp/.docker.xauth
: "${DISPLAY:?DISPLAY is not set -- are you on a headless session?}"

touch "${XAUTH}"
# Re-stamp with a wildcard family so the cookie matches from inside the
# container's network namespace.
xauth nlist "${DISPLAY}" | sed -e 's/^..../ffff/' | xauth -f "${XAUTH}" nmerge -
chmod 644 "${XAUTH}"
echo "xauth cookie ready at ${XAUTH} for DISPLAY=${DISPLAY}"
