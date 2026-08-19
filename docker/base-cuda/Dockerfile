# ---------------------------------------------------------------------------
# ros2-essentials/base-cuda  --  CUDA devel + ROS 2 installed on top
#
# NOTE ON VERSIONS. ROS 2 Humble requires Ubuntu 22.04. NVIDIA does not ship
# 22.04 images for CUDA < 11.7, so a host pinned to CUDA 11.4 (driver ~470)
# cannot run this image. Two options there:
#   (a) keep CUDA workloads out of ROS entirely and talk to them over ZMQ
#       (this is what src/ros_zmq_bridge is for -- the recommended path), or
#   (b) build this FROM nvidia/cuda:11.4.*-ubuntu20.04 and drop to ROS 2 Foxy.
# ---------------------------------------------------------------------------
ARG CUDA_IMAGE=nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04
FROM ${CUDA_IMAGE}
ARG ROS_DISTRO=humble

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    ROS_DISTRO=${ROS_DISTRO}
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      curl gnupg2 lsb-release ca-certificates software-properties-common \
    && add-apt-repository universe -y \
    && curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
         -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
         > /etc/apt/sources.list.d/ros2.list \
    && apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake git sudo nano less iproute2 iputils-ping \
      python3-pip python3-vcstool python3-rosdep \
      python3-colcon-common-extensions \
      ros-${ROS_DISTRO}-ros-base \
      ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
      ros-${ROS_DISTRO}-tf2-ros \
    && rosdep init || true \
    && rm -rf /var/lib/apt/lists/*

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
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics

COPY docker/common/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY docker/common/ws-build      /usr/local/bin/ws-build
COPY docker/common/overlay-build /usr/local/bin/overlay-build
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/ws-build /usr/local/bin/overlay-build

USER ${HOST_UID}:${HOST_GID}
WORKDIR /ws
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
