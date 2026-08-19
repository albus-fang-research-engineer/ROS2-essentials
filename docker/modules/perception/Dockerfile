# ---------------------------------------------------------------------------
# ros2-essentials/perception  --  thin ROS side of the perception boundary
#
# Intent: this image holds the BRIDGE, not the models. Heavy CUDA work
# (FoundationPose, SAM, TRELLIS, cuRobo) stays in its own sidecar containers
# with its own dependency graph, reached over ZMQ. Keeping rclpy out of those
# images is the whole point -- do not let ROS creep in there.
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
      ros-${ROS_DISTRO}-cv-bridge \
      ros-${ROS_DISTRO}-image-transport \
      ros-${ROS_DISTRO}-vision-msgs \
      ros-${ROS_DISTRO}-message-filters \
      python3-opencv \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir pyzmq==26.* msgpack==1.* numpy

ARG HOST_UID=1000
ARG HOST_GID=1000
USER ${HOST_UID}:${HOST_GID}
WORKDIR /ws
