#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Host-side kernel tuning for large DDS samples (camera images).
#
# This is the ONE step in this repo that reaches outside the repo. It touches
# a shared, machine-global setting, so it is a deliberate target rather than
# something `make up` does behind your back.
#
# Requires sudo. Idempotent. Persists across reboots via /etc/sysctl.d.
# ---------------------------------------------------------------------------
set -euo pipefail

CONF=/etc/sysctl.d/60-ros2-dds.conf
WANT_RMEM=16777216

CUR=$(cat /proc/sys/net/core/rmem_max)
echo "net.core.rmem_max is currently ${CUR}"

if [ "${CUR}" -ge "${WANT_RMEM}" ] && [ -f "${CONF}" ]; then
  echo "already tuned, and ${CONF} exists -- nothing to do"
  exit 0
fi

echo "writing ${CONF} (needs sudo)"
sudo tee "${CONF}" >/dev/null <<EOF
# Managed by ros2-essentials: scripts/tune_host.sh
#
# Cyclone DDS asks for a 4MB socket receive buffer (see config/cyclonedds.xml).
# rmem_max is the CEILING on what setsockopt(SO_RCVBUF) may grant; without
# enough headroom here the request is clamped and 2.76 MB camera samples
# arrive incomplete, which silently discards the whole sample.
#
# rmem_default is deliberately NOT raised: that would enlarge the initial
# buffer for every UDP socket on the machine, when only Cyclone needs it.
net.core.rmem_max = ${WANT_RMEM}
EOF

sudo sysctl --system >/dev/null
NEW=$(cat /proc/sys/net/core/rmem_max)
echo "net.core.rmem_max is now ${NEW}"

if [ "${NEW}" -lt "${WANT_RMEM}" ]; then
  echo
  echo "WARNING: the value did not take. On a container host or a VM this can"
  echo "         mean the sysctl is namespaced or read-only. Check for a"
  echo "         conflicting file that sorts AFTER 60-ros2-dds.conf:"
  echo "           grep -rn rmem_max /etc/sysctl.conf /etc/sysctl.d/"
  exit 1
fi

echo
echo "Recreate containers so their DDS sockets are opened against the new"
echo "ceiling -- a running process keeps the buffer it was given at bind time:"
echo "  docker compose up -d --force-recreate"
