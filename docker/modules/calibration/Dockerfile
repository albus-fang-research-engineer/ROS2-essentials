# ---------------------------------------------------------------------------
# ros2-essentials/calibration  --  easy_handeye2 + marker detectors
#
# This module consumes TF ONLY. It does not link against the UR driver or the
# RealSense SDK, which is exactly why it can sit on base-gui rather than
# inheriting from either hardware image.
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
      python3-transforms3d \
      ros-${ROS_DISTRO}-aruco-ros \
      ros-${ROS_DISTRO}-aruco-opencv \
      ros-${ROS_DISTRO}-apriltag-ros \
      ros-${ROS_DISTRO}-image-proc \
      ros-${ROS_DISTRO}-camera-calibration \
      ros-${ROS_DISTRO}-moveit-resources-panda-moveit-config \
      ros-${ROS_DISTRO}-moveit \
    && rm -rf /var/lib/apt/lists/*

ARG HOST_UID=1000
ARG HOST_GID=1000
USER ${HOST_UID}:${HOST_GID}

COPY --chown=${HOST_UID}:${HOST_GID} repos/calibration.repos /tmp/calibration.repos
RUN /usr/local/bin/overlay-build /tmp/calibration.repos

WORKDIR /ws
