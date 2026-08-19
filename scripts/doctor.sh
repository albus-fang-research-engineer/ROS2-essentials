#!/usr/bin/env bash
# Cheap host-side checks for the failure modes that waste the most time.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fail=0
ok()   { echo "  ok    $*"; }
warn() { echo "  WARN  $*"; }
bad()  { echo "  FAIL  $*"; fail=1; }

echo "docker"
command -v docker >/dev/null && ok "docker present" || bad "docker not installed"
docker compose version >/dev/null 2>&1 \
  && ok "compose v2 ($(docker compose version --short 2>/dev/null))" \
  || bad "docker compose v2 not available"
docker info >/dev/null 2>&1 && ok "daemon reachable" \
  || bad "cannot reach docker daemon (are you in the docker group?)"

echo "config"
[ -e "${ROOT}/.env" ] && ok ".env -> $(readlink -f "${ROOT}/.env" | sed "s|${ROOT}/||")" \
  || bad "no .env -- run: make setup"

if [ -e "${ROOT}/.env" ]; then
  # shellcheck disable=SC1091
  set -a; . "${ROOT}/.env"; set +a
  [ "${HOST_UID:-}" = "$(id -u)" ] && ok "HOST_UID matches $(id -u)" \
    || warn "HOST_UID=${HOST_UID:-unset} != $(id -u); src/ will get root-owned files"
  [ -n "${COMPOSE_PROFILES:-}" ] && ok "profiles: ${COMPOSE_PROFILES}" \
    || warn "COMPOSE_PROFILES empty -- 'docker compose up' will start nothing"
  if [ -n "${ROBOT_IP:-}" ]; then
    ping -c1 -W1 "${ROBOT_IP}" >/dev/null 2>&1 \
      && ok "robot ${ROBOT_IP} responds" || warn "robot ${ROBOT_IP} unreachable"
  fi
  CELL="${CELL_NAME:-unnamed-cell}"
  [ -f "${ROOT}/calibrations/${CELL}/extrinsics.yaml" ] \
    && ok "extrinsics present for ${CELL}" \
    || warn "no calibrations/${CELL}/extrinsics.yaml -- the cell profile will refuse to start"
fi

echo "display"
[ -n "${DISPLAY:-}" ] && ok "DISPLAY=${DISPLAY}" || warn "DISPLAY unset (GUI services will fail)"
[ -f /tmp/.docker.xauth ] && ok "xauth cookie present" || warn "run: make x11"

echo "nvidia (only needed for the perception profile)"
if command -v nvidia-smi >/dev/null; then
  ok "driver $(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)"
  docker info 2>/dev/null | grep -qi nvidia && ok "nvidia container runtime registered" \
    || warn "nvidia runtime not visible to docker"
else
  warn "no nvidia-smi (fine unless you run the perception profile)"
fi

echo
[ "$fail" -eq 0 ] && echo "no blocking problems" || echo "blocking problems above"
exit "$fail"
