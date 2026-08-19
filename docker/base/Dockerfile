# ---------------------------------------------------------------------------
# ros2-essentials/base
#
# Deliberately thin. Everything that every module needs and nothing else:
# the distro, a sane DDS, colcon tooling, a UID-matched user, the entrypoint.
#
# Anything hardware- or task-specific belongs in docker/modules/*.
# ---------------------------------------------------------------------------
ARG ROS_DISTRO=humble
FROM ros:${ROS_DISTRO}-ros-base AS base
ARG ROS_DISTRO

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    ROS_DISTRO=${ROS_DISTRO}
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake git curl wget nano less sudo \
      iputils-ping iproute2 net-tools \
      python3-pip python3-vcstool python3-rosdep \
      python3-colcon-common-extensions python3-colcon-mixin \
      ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
      ros-${ROS_DISTRO}-tf2-ros ros-${ROS_DISTRO}-tf2-tools \
    && rm -rf /var/lib/apt/lists/*

# --- UID-matched user -------------------------------------------------------
# /ws is bind-mounted from the host. Building as root leaves you with
# root-owned build/ install/ log/ trees that you cannot rm without sudo.
ARG USERNAME=ros
ARG HOST_UID=1000
ARG HOST_GID=1000
RUN if ! getent group ${HOST_GID} >/dev/null; then groupadd -g ${HOST_GID} ${USERNAME}; fi \
 && useradd -o -m -u ${HOST_UID} -g ${HOST_GID} -d /home/${USERNAME} -s /bin/bash ${USERNAME} \
 && usermod -aG video,plugdev,dialout,sudo ${USERNAME} \
 && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/99-${USERNAME} \
 && chmod 0440 /etc/sudoers.d/99-${USERNAME} \
 && mkdir -p /home/${USERNAME}/.ros2 /ws/src /opt/overlay \
 && chown -R ${HOST_UID}:${HOST_GID} /home/${USERNAME} /ws /opt/overlay

ENV WS=/ws \
    OVERLAY_WS=/opt/overlay \
    HOME=/home/${USERNAME} \
    RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
    ROS_LOCALHOST_ONLY=0 \
    RCUTILS_COLORIZED_OUTPUT=1 \
    RCUTILS_CONSOLE_OUTPUT_FORMAT="[{severity}] [{name}]: {message}"


# Make interactive shells working ROS shells. Written to BOTH ~/.bashrc
# (docker exec -it ... bash) and /etc/profile.d (login shells): neither
# covers the other, and people reach for both.
RUN cat > /etc/profile.d/10-ros2-essentials.sh <<'RCEOF'
# --- ros2-essentials -------------------------------------------------------
# The ENTRYPOINT sources these, but `docker exec -it <container> bash` does NOT
# run the entrypoint: it starts a fresh process from the image rather than a
# child of PID 1. Without this, an exec'd shell has no ros2 on PATH at all.
if [ -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]; then
  . "/opt/ros/${ROS_DISTRO}/setup.bash"
fi
if [ -n "${OVERLAY_WS:-}" ] && [ -f "${OVERLAY_WS}/install/setup.bash" ]; then
  . "${OVERLAY_WS}/install/setup.bash"
fi
if [ -n "${WS:-}" ] && [ -f "${WS}/install/setup.bash" ]; then
  . "${WS}/install/setup.bash"
fi
if [ -f /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash ]; then
  . /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash
fi
# Which container am I in, and on which DDS domain? Saves a lot of confusion
# when several stacks are up and one of them is on the wrong domain.
echo "ros2-essentials | ${ROS_DISTRO} | domain ${ROS_DOMAIN_ID:-0} | rmw ${RMW_IMPLEMENTATION:-default}"
RCEOF
RUN chmod 0644 /etc/profile.d/10-ros2-essentials.sh \
 && cat /etc/profile.d/10-ros2-essentials.sh >> /home/${USERNAME}/.bashrc \
 && chown ${HOST_UID}:${HOST_GID} /home/${USERNAME}/.bashrc

COPY docker/common/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY docker/common/ws-build      /usr/local/bin/ws-build
COPY docker/common/overlay-build /usr/local/bin/overlay-build
RUN chmod +x /usr/local/bin/entrypoint.sh \
             /usr/local/bin/ws-build \
             /usr/local/bin/overlay-build

USER ${HOST_UID}:${HOST_GID}
WORKDIR /ws
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
