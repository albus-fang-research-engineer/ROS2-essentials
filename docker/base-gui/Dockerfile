# ---------------------------------------------------------------------------
# ros2-essentials/base-gui  --  base + X11 + rviz/rqt
#
# Split out from base so that headless modules (drivers, perception sidecars)
# do not carry ~1.5 GB of Qt they will never open.
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
      libgl1-mesa-glx libgl1-mesa-dri libxkbcommon-x11-0 \
      x11-apps mesa-utils \
      ros-${ROS_DISTRO}-rviz2 \
      ros-${ROS_DISTRO}-rqt-gui ros-${ROS_DISTRO}-rqt-gui-py \
      ros-${ROS_DISTRO}-rqt-common-plugins \
      ros-${ROS_DISTRO}-rqt-image-view \
      ros-${ROS_DISTRO}-rqt-tf-tree \
      ros-${ROS_DISTRO}-joint-state-publisher-gui \
    && rm -rf /var/lib/apt/lists/*

ENV QT_X11_NO_MITSHM=1

ARG HOST_UID=1000
ARG HOST_GID=1000
USER ${HOST_UID}:${HOST_GID}
WORKDIR /ws
