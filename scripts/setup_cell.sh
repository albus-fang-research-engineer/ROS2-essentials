#!/usr/bin/env bash
# Point .env at this machine's cell config, creating one from the template if
# this is a new bench. A machine's identity lives in cells/<name>.env; the repo
# itself is identical everywhere.
set -euo pipefail

CELL="${1:-$(hostname)}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${ROOT}/cells/${CELL}.env"

if [ ! -f "${TARGET}" ]; then
  echo "no cells/${CELL}.env -- creating from the example"
  sed -e "s/^CELL_NAME=.*/CELL_NAME=${CELL}/" \
      "${ROOT}/cells/example-ur5e-01.env" > "${TARGET}"
  echo "EDIT cells/${CELL}.env before running anything: robot IP, camera"
  echo "serial, marker size, and COMPOSE_PROFILES are all machine-specific."
fi

ln -sfn "cells/${CELL}.env" "${ROOT}/.env"

# UID/GID must match the host user or the bind-mounted src/ fills with
# root-owned build artefacts.
if grep -q '^HOST_UID=' "${TARGET}"; then
  sed -i "s/^HOST_UID=.*/HOST_UID=$(id -u)/" "${TARGET}"
  sed -i "s/^HOST_GID=.*/HOST_GID=$(id -g)/" "${TARGET}"
else
  printf '\nHOST_UID=%s\nHOST_GID=%s\n' "$(id -u)" "$(id -g)" >> "${TARGET}"
fi

mkdir -p "${ROOT}/calibrations/${CELL}"
echo ".env -> cells/${CELL}.env"
grep -E '^(CELL_NAME|COMPOSE_PROFILES|ROBOT_IP|HOST_UID)=' "${TARGET}" || true
