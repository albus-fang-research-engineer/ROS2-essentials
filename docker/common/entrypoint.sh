#!/usr/bin/env bash
# Layer the three workspaces, then exec whatever the service asked for.
set -e

source "/opt/ros/${ROS_DISTRO}/setup.bash"

# Module overlay baked into the image at build time (easy_handeye2, etc).
if [ -f "${OVERLAY_WS}/install/setup.bash" ]; then
  source "${OVERLAY_WS}/install/setup.bash"
fi

# Your packages, bind-mounted from the host. Built with `make ws`.
if [ -f "${WS}/install/setup.bash" ]; then
  source "${WS}/install/setup.bash"
fi

exec "$@"
