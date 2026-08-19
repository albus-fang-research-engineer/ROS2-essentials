# ROS2-essentials

A single repo that runs on every machine with hardware attached to it. Same
files on the manipulator bench and the GPU box; the only difference is which
**profiles** that machine turns on.

```
docker/base            distro + CyclomeDDS + colcon + UID-matched user
  ├── base-gui         + X11, rviz, rqt
  │     ├── calibration    easy_handeye2, aruco/apriltag/charuco detectors
  │     └── tools          rviz, rosbag, foxglove, plotjuggler
  ├── ur               UR driver, ur_calibration, MoveIt
  ├── realsense        librealsense + image pipeline
  └── perception       the ROS<->ZMQ bridge only (no models, no CUDA)
docker/base-cuda       CUDA devel + ROS, for when a node genuinely needs both
```

## Quick start

```bash
git clone git@github.com:albus-fang-research-engineer/ROS2-essentials.git
cd ROS2-essentials

make setup          # links .env -> cells/$(hostname).env, preps X11 cookie
$EDITOR cells/$(hostname).env    # robot IP, camera serial, COMPOSE_PROFILES
make doctor         # checks the things that waste the most time
make build          # base -> base-gui -> modules, in order
make ws             # colcon build the packages in src/
make up             # starts whatever COMPOSE_PROFILES lists
```

Verify the calibration stack with no hardware at all:

```bash
make demo
```

## The three ideas this is built on

**Image boundaries follow hardware, not dependencies.** `easy_handeye2` consumes
TF only — it never links against the UR driver or the RealSense SDK. So the
calibration image inherits from `base-gui`, not from either hardware image.
Most ROS modules talk over DDS rather than over shared libraries, which is what
makes this possible; the exceptions (anything using `ros2_control` hardware
interfaces) do need to share an image with their driver.

**Profiles are machine identity.** `cells/<hostname>.env` sets
`COMPOSE_PROFILES`. The manipulator bench runs `ur,camera,cell`; the GPU box
runs `perception,cell`; on calibration day the bench runs
`ur,camera,calib,viz`. `docker compose up` on any machine does the right thing
with no arguments.

**Calibration has a producer and a consumer, and they should not be the same
stack.** The producer (`calib` profile) runs a few times a year, interactively,
with a GUI and the whole rig powered up. The consumer (`cell` profile) runs on
every boot of everything and needs seven numbers. `scripts/promote_calibration.py`
is the deliberate, auditable step between them.

## Layout

| Path | What it is |
|---|---|
| `docker/base*/` | Base images. Change here, rebuild everything. |
| `docker/modules/` | One Dockerfile per hardware or task module. |
| `docker/common/` | `entrypoint.sh` (workspace layering), build helpers. |
| `docker-compose.yml` | Every service. Module boundary = profile name. |
| `cells/` | One `.env` per physical machine. Committed. |
| `calibrations/` | Per-cell extrinsics + archived `.calib`. **Committed.** |
| `config/` | Cyclone XML, rviz configs, extracted UR kinematics. |
| `repos/` | `.repos` files for source-built overlays. |
| `src/` | Your ROS packages, bind-mounted into every container. |
| `scripts/` | Host-side: setup, X11, doctor, calibration promotion. |

### Packages in `src/`

- **`cell_description`** — reads `calibrations/<cell>/extrinsics.yaml` and
  publishes every calibrated transform in the cell as static TF. The single
  source of truth that MoveIt, rviz, and the ZMQ sidecars all agree on.
- **`handeye_bringup`** — marker tracker with your topics and frames baked in,
  plus a combined tracker + `easy_handeye2` launch.
- **`ros_zmq_bridge`** — the one node that speaks ROS on behalf of the CUDA
  sidecars. Serves synchronised colour + depth + intrinsics + TF snapshots over
  ZMQ so `FoundationPose`, `SAM`, `TRELLIS`, and `cuRobo` containers never need
  `rclpy` in their already-fragile dependency graphs.

## Calibration workflow

```bash
# 1. ONCE per arm. Uncorrected DH deltas put mm-level error into FK, and
#    hand-eye has no way to separate that from the extrinsic.
make kinematics

# 2. Bring the hardware up, then the calibration GUI.
COMPOSE_PROFILES=ur,camera docker compose up -d
make calibrate

# 3. Jog to ~15-20 poses, "Take Sample" at each, then Compute and Save.
#    Rotate the flange as far as joint limits allow about ALL THREE axes, in
#    both directions. Translation-only samples leave the rotation estimate
#    rank deficient and the solve will be confidently wrong.

# 4. Promote the result into the cell's geometry.
make promote CALIB=~/.ros2/easy_handeye2/calibrations/ur5e_d435_eob.calib

# 5. The cell profile now publishes it on every boot.
docker compose --profile cell up -d --force-recreate cell
```

## Adding a module

1. `docker/modules/<name>/Dockerfile`, `FROM ros2-essentials/base:${TAG}` (or
   `base-gui` if it opens a window, `base-cuda` if it genuinely needs both ROS
   and CUDA in one process).
2. A `<name>:` target in the `Makefile` with the correct base as a prerequisite.
3. One service block in `docker-compose.yml` with `profiles: [<name>]`.
4. Add the profile to whichever `cells/*.env` should run it.

## Things that will bite

- **Frame names take no leading slash.** Upstream `easy_handeye2` docs still
  show `/base_link`; that is ROS 1 legacy and ROS 2 `tf2` rejects it.
- **UR frames.** `base_link` is the URDF root; `base` is the ROS-Industrial
  rotated frame. Mixing them costs a 180° yaw that looks almost plausible.
- **Measure the marker.** `MARKER_SIZE` is the black square edge in metres, and
  printers lie about scale. A 2% size error is a 2% range bias no number of
  extra samples will average away.
- **Two NICs, one Cyclone.** With a robot NIC and a lab NIC, pin the interface
  in `config/cyclonedds.xml` or discovery will intermittently pick wrong.
- **A sourced ROS install on the host poisons the build.** If your `.bashrc`
  sources `/opt/ros/noetic/setup.bash`, your shell exports `ROS_DISTRO=noetic`
  — and both make's `?=` and compose's `${VAR:-default}` treat an exported
  variable as already-set. A bare `ROS_DISTRO` in this repo would silently
  build `FROM ros:noetic-ros-base`. That is why every host-facing knob here is
  `R2E_*` (`R2E_DISTRO`, `R2E_DOMAIN_ID`, `R2E_RMW`, `R2E_CYCLONEDDS_URI`) and
  only becomes `ROS_DISTRO` etc. inside the container. `make doctor` flags it.
- **These images are local-only.** Compose responds to a missing image by
  trying to pull it, so a failed build surfaces later as `pull access denied
  for ros2-essentials/...`. The `require-*` guards in the Makefile catch this
  and tell you which `make` target you actually skipped.
- **`HOST_UID` must match you.** Otherwise `src/` fills with root-owned
  `build/` and `install/` trees. `make doctor` checks this.
- **CUDA 11.4 hosts cannot run `base-cuda`.** NVIDIA ships no 22.04 image below
  CUDA 11.7, and ROS 2 Humble needs 22.04. Keep CUDA work in ZMQ sidecars —
  which is what `ros_zmq_bridge` is for — rather than fighting this.

## Compose note

Everything lives in one `docker-compose.yml` rather than per-module fragments
under `compose/`. Compose's `include:` resolves relative paths against the
*included* file's directory, so `./src:/ws/src` inside `compose/ur.yml`
silently becomes `compose/src`. `project_directory:` patches it, but then
`extends:` resolution gets murky. Past ~15 services, revisit — with that caveat
in hand.
