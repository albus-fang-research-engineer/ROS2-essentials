# ---------------------------------------------------------------------------
# ros2-essentials/ur  --  Universal Robots driver + MoveIt
# All apt. Nothing built from source, so this image is cheap to rebuild.
# ---------------------------------------------------------------------------
ARG ROS_DISTRO=humble
ARG TAG=dev
FROM ros2-essentials/base:${TAG}
ARG ROS_DISTRO

USER root
ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      ros-${ROS_DISTRO}-ur \
      ros-${ROS_DISTRO}-ur-robot-driver \
      ros-${ROS_DISTRO}-ur-description \
      ros-${ROS_DISTRO}-ur-moveit-config \
      ros-${ROS_DISTRO}-ur-calibration \
      ros-${ROS_DISTRO}-moveit \
      ros-${ROS_DISTRO}-robot-state-publisher \
      ros-${ROS_DISTRO}-joint-state-broadcaster \
      ros-${ROS_DISTRO}-controller-manager \
    && rm -rf /var/lib/apt/lists/*

ARG HOST_UID=1000
ARG HOST_GID=1000
USER ${HOST_UID}:${HOST_GID}
WORKDIR /ws
