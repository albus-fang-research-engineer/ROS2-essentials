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
make host-tune      # ONE-OFF, sudo: kernel socket buffers for image topics
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

Each step has a check before it. Every one of these catches a failure that is
invisible until you have already spent twenty minutes sampling.

### 0. Configure the cell, once

In `cells/<hostname>.env`:

```
COMPOSE_PROFILES=ur,camera,calib     # drop `cell` -- it exits 2 with no extrinsics yet
ROBOT_IP=<from the teach pendant, Settings > System > Network>
CALIB_TYPE=eye_on_base               # or eye_in_hand
CALIB_NAME=ur5e_d435_eob
MARKER_SIZE=<black square edge, in METRES, measured with calipers>
MARKER_ID=<an id valid in the dictionary you printed from>
CAMERA_TF_ROOT=camera_link           # solve for this, NOT an optical frame
```

Find the robot IP from the host if the pendant is not handy — every UR
controller answers on TCP 29999:

```bash
ip -brief addr                             # which interface is on the robot subnet?
nmap -p 29999 --open -T4 10.0.0.0/24       # substitute the real subnet
nc <ip> 29999                              # greets you with the dashboard banner
```

### 1. Arm kinematics, once per arm

```bash
make kinematics       # writes config/ur_kinematics.yaml
```

Not optional. Uncorrected DH deltas put mm-level error into FK, and hand-eye
has no way to separate that from the extrinsic — it lands in your result.

### 2. Bring up the hardware, then verify both halves

```bash
docker compose up -d ur camera
```

```bash
# robot side: does FK reach the flange?
docker compose --profile shell run --rm shell bash -lc \
  'ros2 run tf2_ros tf2_echo base_link tool0'

# camera side: are frames actually flowing?
docker compose --profile shell run --rm shell bash -lc \
  'ros2 topic hz /camera/camera/color/image_raw'

# camera subtree intact, exactly one parent for camera_link?
docker compose --profile shell run --rm shell bash -lc \
  'ros2 run tf2_ros tf2_echo camera_link camera_color_optical_frame'
```

### 3. Mount the target, then confirm it is detected

You need two numbers: which **id** to track, and the **physical size** of the
black square. Neither can be guessed; neither has to be.

This `aruco_ros` build exposes no `dictionary` parameter, so the dictionary is
fixed at the vendored library's default — and a marker from the wrong one is
never detected, silently, with no warning of any kind.

**If you already have a marker or board**, ask the detector what it sees rather
than guessing:

```bash
make marker-picker
```

That opens a live annotated view with every detected marker outlined and its id
drawn on it, plus a console readout of how often each id is detected. Move the
board around the workspace and pick an id that stays near 100% — an id seen in
40% of frames will make sampling miserable long before it makes the solve
wrong. Anything it outlines is by definition in the right dictionary.

**If you don't**, print a candidate sheet: the same id rendered from each
plausible dictionary, two columns, sized for A4/Letter.

```bash
make marker SIZE=0.06        # writes marker_sheet.png
```

Print at **100% / Actual size**, never "fit to page". Check the 100 mm bar with
a ruler before anything else — if it isn't 100 mm the printer rescaled and every
marker on the page is the wrong size. Then hold the sheet up with the tracker
running: exactly one tile gets outlined in `/aruco_single/result`. That
identifies your dictionary and confirms the id is valid in it.

Print the real target from that dictionary, larger — a bigger marker is a
better-conditioned pose estimate:

```bash
make marker SIZE=0.10 ID=42 DICT=ARUCO_ORIGINAL
```

Mount it **rigidly**. A marker that flexes relative to the flange is
unrecoverable noise — glue or bolt it to a flat plate, don't tape paper to
something curved. Then measure its black square with calipers and put that
value, in metres, in `MARKER_SIZE`. Not the nominal `SIZE` you asked for: what
the printer actually produced. A 2% size error is a 2% range bias that no number
of extra samples will average away.

```bash
docker compose --profile calib up tracker
```

```bash
# annotated debug stream: a detected marker gets drawn on
docker compose --profile shell run --rm shell bash -lc \
  'ros2 run rqt_image_view rqt_image_view /aruco_single/result'

# and it should appear in tf, moving when you move the arm
docker compose --profile shell run --rm shell bash -lc \
  'ros2 run tf2_ros tf2_echo camera_link aruco_marker_frame'
```

Nothing drawn means the wrong dictionary, wrong `MARKER_ID`, or
`min_marker_size` rejecting it as too small. That is a printing problem, not a
calibration problem — fix it here.

### 4. Sample

```bash
make calibrate
```

Put the arm in freedrive. At each pose: check the marker is clearly in frame,
then **Take Sample**. 15–20 poses.

**Rotate the flange as far as joint limits allow about all three axes, in both
directions.** This is the single thing that determines whether the result is
any good. Translation-only samples leave the rotation estimate rank deficient
and the solve comes back confident and wrong. Vary distance and where the
marker sits in the image too — corners as well as centre.

Then **Compute**, then **Save**.

### 5. Promote

```bash
make promote CALIB=~/.ros2/easy_handeye2/calibrations/ur5e_d435_eob.calib
```

Read the `|t|` line it prints. If the distance is nothing like where the camera
physically sits, that is a frame-convention mistake (`base_link` vs `base`),
not a bad solve. The script refuses outright to write an `*_optical_frame`
child — see the TF-tree note in Gotchas.

### 6. Put `cell` back and verify

Add `cell` to `COMPOSE_PROFILES`, then:

```bash
docker compose --profile cell up -d --force-recreate cell
docker compose --profile shell run --rm shell bash -lc \
  'ros2 run tf2_ros tf2_echo base_link camera_color_optical_frame'
```

Sanity-check against reality: put the marker somewhere you can measure, and
confirm its position in `base_link` matches a tape measure to within a few mm.
A calibration that solves cleanly but is wrong by a fixed offset will otherwise
not surface until a grasp misses.

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
- **Launch args cannot take an empty value.** `serial_no:=` with nothing after
  it is a parse error, not an omission — so any optional launch argument must
  be passed as a whole token (`CAMERA_EXTRA_ARGS`), never as a variable that
  expands to nothing inside one. Camera serials also need a leading underscore
  (`serial_no:=_912112073098`) or the parser reads them as numbers.
- **Never solve for an optical frame.** The camera driver already publishes
  `camera_link -> camera_color_frame -> camera_color_optical_frame`. If the
  calibration targets the optical frame and you publish that result, the
  optical frame gets a second parent, TF stops being a tree, and lookups go
  non-deterministic. `aruco_ros` separates `camera_frame` (intrinsics /
  projection) from `reference_frame` (what the pose is reported in), so
  `CAMERA_TF_ROOT=camera_link` makes the solve target the driver's root link
  directly — no post-hoc composition, and nothing to redo if you switch
  between the colour and depth optical frames. `promote_calibration.py`
  refuses to write an optical-frame child.
- **Measure the marker.** `MARKER_SIZE` is the black square edge in metres, and
  printers lie about scale. A 2% size error is a 2% range bias no number of
  extra samples will average away.
- **The DDS socket buffer needs BOTH halves, and bites you either way if it
  only has one.** A `min` in `cyclonedds.xml` that the kernel cannot grant
  (capped by `net.core.rmem_max`, 212992 bytes by default) makes Cyclone fail
  domain creation, and every node dies with `rmw_create_node: failed to create
  domain, error Error` — which names neither the buffer nor the config file.
  But deleting the `min` does not fix that, it only makes the failure quiet:
  `rmem_max` is a *ceiling* on what `setsockopt(SO_RCVBUF)` may grant, so with
  no request every socket comes up at `rmem_default` regardless. Symptom of the
  quiet version: 1280x720 rgb8 is 2.76 MB, fragmented into ~43 datagrams
  arriving as one burst 30 times a second, so almost every sample lands
  incomplete — and one lost fragment discards the *whole* sample.
  **`ros2 topic echo` still works** (reliable readers repair by retransmit, at a
  degraded rate with multi-hundred-ms stalls) **while rviz's Image display shows
  one frame and then freezes** (best effort, no repair). That split is the
  signature; do not read a working `echo` as a healthy stream. `make host-tune`
  raises the ceiling, `config/cyclonedds.xml` makes the request, and
  `make doctor` compares the two numbers.
- **Confirm packet loss with the right counter.** `netstat -su`'s "packet
  receive errors" lumps buffer overruns in with checksum and no-port errors.
  `nstat -az | grep -i UdpRcvbufErrors` isolates the one that matters, and
  `ss -uapm` shows the buffer a live socket actually got (`rb:` — you want
  millions, not 212992).
- **Do not fix an image display by setting it to Reliable.** It works, which is
  why it is tempting, and it is a diagnostic rather than a fix. A reliable
  reader makes the writer hold samples until they are acked, so a slow
  subscriber (rviz on llvmpipe — the `viz` service gets no `/dev/dri`) fills the
  writer history cache and blocks `publish()` in the camera node for *every*
  consumer, tracker included. A viewer must never be able to throttle a sensor
  driver. Keep `Reliability Policy: Best Effort` in `cell.rviz` and fix the
  buffer instead. rviz rewrites its config on exit, so check
  `git diff config/rviz/` before committing after a debugging session.
- **Two NICs, one Cyclone.** With a robot NIC and a lab NIC, pin the interface
  in `config/cyclonedds.xml` or discovery will intermittently pick wrong.
- **Container env is frozen at create time.** Editing `cells/<host>.env`
  changes nothing about containers that already exist — `ROS_DOMAIN_ID` and
  friends are baked in when the container is *created*, not read at each
  start. A stack half-migrated this way ends up with services on two different
  DDS domains that cannot see each other, and nothing reports an error. After
  any cell-file change: `docker compose up -d --force-recreate`. `make doctor`
  compares every running container against the cell file.
- **A sourced ROS install on the host poisons the build.** If your `.bashrc`
  sources `/opt/ros/noetic/setup.bash`, your shell exports `ROS_DISTRO=noetic`
  — and both make's `?=` and compose's `${VAR:-default}` treat an exported
  variable as already-set. A bare `ROS_DISTRO` in this repo would silently
  build `FROM ros:noetic-ros-base`. That is why every host-facing knob here is
  `R2E_*` (`R2E_DISTRO`, `R2E_DOMAIN_ID`, `R2E_RMW`, `R2E_CYCLONEDDS_URI`) and
  only becomes `ROS_DISTRO` etc. inside the container. `make doctor` flags it.
- **rviz resolves meshes locally, not over DDS.** `robot_state_publisher` in
  the `ur` service latches the URDF, so rviz gets the *text* wherever it runs
  — but every `package://ur_description/...` URI in that text is looked up in
  the ament index of rviz's own container. The `tools` image is not a UR
  image, so `ur_description` has to be installed there too or rviz logs
  `Package [ur_description] does not exist` for every link and shows an empty
  RobotModel. Same trap for any other robot whose description you view.
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
