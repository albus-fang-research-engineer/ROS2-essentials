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

echo "host environment"
if [ -n "${ROS_DISTRO:-}" ]; then
  bad "ROS_DISTRO=${ROS_DISTRO} is exported by your shell"
  echo "        A sourced ROS install leaks into make (?=) and compose"
  echo "        (\${VAR:-default}) and silently picks the wrong base image."
  echo "        This repo uses R2E_DISTRO instead, but anything else reading"
  echo "        ROS_DISTRO on the host will still be confused. Consider not"
  echo "        sourcing /opt/ros/*/setup.bash from .bashrc on a Docker host."
else
  ok "no ROS_DISTRO leaking from the shell"
fi
for v in ROS_DOMAIN_ID RMW_IMPLEMENTATION CYCLONEDDS_URI ROS_MASTER_URI; do
  [ -n "${!v:-}" ] && warn "$v=${!v} exported by your shell (repo uses R2E_$v style names)"
done
[ -n "${CONDA_PREFIX:-}" ] && warn "conda env active (${CONDA_DEFAULT_ENV:-?}); harmless for docker, but its libtinfo shadows the system one and spams warnings"

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

  # A cell file generated before the R2E_* rename keeps the old key names,
  # which compose silently ignores -- the values look set but never apply.
  STALE=$(grep -oE '^(ROS_DISTRO|ROS_DOMAIN_ID|RMW_IMPLEMENTATION|CYCLONEDDS_URI|CAMERA_SERIAL)=' \
            "$(readlink -f "${ROOT}/.env")" 2>/dev/null | tr -d '=' | tr '\n' ' ')
  if [ -n "${STALE}" ]; then
    bad "stale keys in your cell file: ${STALE}"
    echo "        compose reads R2E_DISTRO / R2E_DOMAIN_ID / R2E_RMW /"
    echo "        R2E_CYCLONEDDS_URI / CAMERA_EXTRA_ARGS. The old names are"
    echo "        ignored, so those settings are silently not applied."
  else
    ok "cell file uses current key names"
  fi

  # A hard socket-buffer minimum in cyclonedds.xml that the kernel cannot meet
  # kills domain creation for every node with an opaque error.
  CDDS="${ROOT}/config/cyclonedds.xml"
  if [ -f "${CDDS}" ] && grep -qE 'MinimumSocketReceiveBufferSize|SocketReceiveBufferSize[^>]*min=' "${CDDS}"; then
    RMEM=$(cat /proc/sys/net/core/rmem_max 2>/dev/null || echo 0)
    warn "cyclonedds.xml requests a socket buffer minimum; host rmem_max=${RMEM}"
    echo "        If it exceeds rmem_max, every node fails with"
    echo "        'rmw_create_node: failed to create domain'."
  fi
fi

echo "running containers"
if command -v docker >/dev/null 2>&1 && [ -n "${R2E_DOMAIN_ID:-}" ]; then
  MISMATCH=0
  for c in $(docker ps --format '{{.Names}}' 2>/dev/null); do
    CDOM=$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$c" 2>/dev/null \
             | sed -n 's/^ROS_DOMAIN_ID=//p')
    [ -z "$CDOM" ] && continue
    if [ "$CDOM" != "${R2E_DOMAIN_ID}" ]; then
      bad "$c is on ROS_DOMAIN_ID=$CDOM but the cell says ${R2E_DOMAIN_ID}"
      MISMATCH=1
    fi
  done
  if [ "$MISMATCH" = 1 ]; then
    echo "        Container env is fixed when the container is CREATED, not"
    echo "        read at each start. Editing the cell file does nothing to"
    echo "        containers that already exist:"
    echo "          docker compose up -d --force-recreate"
  else
    ok "running containers agree on domain ${R2E_DOMAIN_ID}"
  fi
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
