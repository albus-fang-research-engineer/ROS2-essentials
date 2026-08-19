# ---------------------------------------------------------------------------
# ros2-essentials/tools  --  rviz, rosbag, plotjuggler, foxglove bridge
# The image you shell into when something is wrong.
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
    && rm -rf /var/lib/apt/lists/*

ARG HOST_UID=1000
ARG HOST_GID=1000
USER ${HOST_UID}:${HOST_GID}
WORKDIR /ws
