# ---------------------------------------------------------------------------
# ros2-essentials/realsense  --  librealsense2 + realsense2_camera
#
# Swapping sensors means swapping this file only. The contract with everything
# downstream is: image_raw + camera_info + a TF for the optical frame.
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
      ros-${ROS_DISTRO}-realsense2-camera \
      ros-${ROS_DISTRO}-realsense2-description \
      ros-${ROS_DISTRO}-image-proc \
      ros-${ROS_DISTRO}-image-transport-plugins \
      ros-${ROS_DISTRO}-depth-image-proc \
      ros-${ROS_DISTRO}-camera-calibration \
      ros-${ROS_DISTRO}-camera-calibration-parsers \
    && rm -rf /var/lib/apt/lists/*

ARG HOST_UID=1000
ARG HOST_GID=1000
USER ${HOST_UID}:${HOST_GID}
WORKDIR /ws
