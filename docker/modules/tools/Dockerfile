# ---------------------------------------------------------------------------
# ros2-essentials/tools  --  rviz, rosbag, plotjuggler, foxglove bridge
# The image you shell into when something is wrong.
#
# ur_description is here because MESHES ARE DATA, NOT HARDWARE. The URDF text
# reaches rviz over DDS from the `ur` service, but every package:// URI inside
# it is resolved against the ament index of the container rviz runs in. This
# image is not a UR image, so without the description package rviz logs
# `Package [ur_description] does not exist` once per link and draws nothing.
# The alternative -- running rviz out of the `ur` image -- would drag the whole
# driver into the viz profile on machines that have no arm attached.
# ---------------------------------------------------------------------------
ARG ROS_DISTRO=humble
ARG TAG=dev
FROM ros2-essentials/base-gui:${TAG}
ARG ROS_DISTRO

USER root
ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      ros-${ROS_DISTRO}-rosbag2 \
      ros-${ROS_DISTRO}-rosbag2-storage-mcap \
      ros-${ROS_DISTRO}-foxglove-bridge \
      ros-${ROS_DISTRO}-plotjuggler-ros \
      ros-${ROS_DISTRO}-topic-tools \
      ros-${ROS_DISTRO}-rqt-graph \
      ros-${ROS_DISTRO}-rqt-reconfigure \
      ros-${ROS_DISTRO}-ur-description \
    && rm -rf /var/lib/apt/lists/*

ARG HOST_UID=1000
ARG HOST_GID=1000
USER ${HOST_UID}:${HOST_GID}
WORKDIR /ws
