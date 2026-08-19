# ===========================================================================
# ros2-essentials
#
# Compose does not order builds by FROM dependency, so image builds go through
# here: base -> base-gui -> modules. Everything else is convenience.
# ===========================================================================

SHELL := /bin/bash
ROS_DISTRO ?= humble
TAG        ?= dev
HOST_UID   := $(shell id -u)
HOST_GID   := $(shell id -g)
CELL       ?= $(shell hostname)

BUILD_ARGS = --build-arg ROS_DISTRO=$(ROS_DISTRO) \
             --build-arg TAG=$(TAG) \
             --build-arg HOST_UID=$(HOST_UID) \
             --build-arg HOST_GID=$(HOST_GID)

.DEFAULT_GOAL := help

# --- setup ------------------------------------------------------------------

.PHONY: setup
setup: ## First-run: link .env to this machine's cell config, prep X11
	@scripts/setup_cell.sh $(CELL)
	@scripts/x11_setup.sh

.PHONY: x11
x11: ## Refresh the X11 cookie (once per login session)
	@scripts/x11_setup.sh

# --- images -----------------------------------------------------------------

.PHONY: build
build: base base-gui ur realsense calibration tools ## Build every image, in order

.PHONY: base
base: ## Thin base: distro + cyclone + colcon + user
	docker build $(BUILD_ARGS) -f docker/base/Dockerfile \
		-t ros2-essentials/base:$(TAG) .

.PHONY: base-gui
base-gui: base ## base + X11 + rviz/rqt
	docker build $(BUILD_ARGS) -f docker/base-gui/Dockerfile \
		-t ros2-essentials/base-gui:$(TAG) .

.PHONY: base-cuda
base-cuda: ## CUDA devel + ROS 2 (see the version note in the Dockerfile)
	docker build $(BUILD_ARGS) -f docker/base-cuda/Dockerfile \
		-t ros2-essentials/base-cuda:$(TAG) .

.PHONY: ur realsense calibration tools perception
ur: base ## UR driver + MoveIt
	docker build $(BUILD_ARGS) -f docker/modules/ur/Dockerfile \
		-t ros2-essentials/ur:$(TAG) .

realsense: base ## RealSense driver + image pipeline
	docker build $(BUILD_ARGS) -f docker/modules/realsense/Dockerfile \
		-t ros2-essentials/realsense:$(TAG) .

calibration: base-gui ## easy_handeye2 + marker detectors
	docker build $(BUILD_ARGS) -f docker/modules/calibration/Dockerfile \
		-t ros2-essentials/calibration:$(TAG) .

tools: base-gui ## rviz, rosbag, foxglove, plotjuggler
	docker build $(BUILD_ARGS) -f docker/modules/tools/Dockerfile \
		-t ros2-essentials/tools:$(TAG) .

perception: base ## ROS side of the ZMQ perception boundary
	docker build $(BUILD_ARGS) -f docker/modules/perception/Dockerfile \
		-t ros2-essentials/perception:$(TAG) .

# --- workspace --------------------------------------------------------------

.PHONY: ws
ws: ## colcon build the bind-mounted workspace in src/
	docker compose --profile shell run --rm shell ws-build

.PHONY: ws-clean
ws-clean: ## Remove colcon artefacts from src/ (they are gitignored, not tracked)
	rm -rf build install log

# --- running ----------------------------------------------------------------

.PHONY: up down ps logs
up: ## Bring up whatever COMPOSE_PROFILES says this machine runs
	docker compose up -d
	@docker compose ps

down: ## Stop everything, all profiles
	docker compose --profile ur --profile camera --profile calib \
	               --profile cell --profile viz --profile perception \
	               --profile moveit --profile shell --profile demo down

ps: ## Running services
	docker compose ps

logs: ## Tail all logs
	docker compose logs -f --tail=100

.PHONY: shell
shell: ## Interactive shell in the tools image
	docker compose --profile shell run --rm shell bash

# --- calibration workflow ---------------------------------------------------

.PHONY: kinematics
kinematics: ## ONE-SHOT: pull the arm's factory DH deltas into config/
	docker compose --profile oneshot run --rm ur-kinematics

.PHONY: calibrate
calibrate: ## Interactive hand-eye calibration (needs ur + camera already up)
	docker compose --profile calib up

.PHONY: promote
promote: ## Promote a .calib into the cell extrinsics: make promote CALIB=path/to.calib
	@test -n "$(CALIB)" || (echo "usage: make promote CALIB=<path to .calib>"; exit 1)
	scripts/promote_calibration.py --calib "$(CALIB)" --cell "$(CELL)"

.PHONY: demo
demo: ## Offline calibration smoke test, no hardware
	docker compose --profile demo up handeye-demo

# --- introspection ----------------------------------------------------------

.PHONY: tf
tf: ## Dump the current TF tree to /tmp
	docker compose --profile shell run --rm shell \
		bash -lc 'cd /tmp && ros2 run tf2_tools view_frames'

.PHONY: doctor
doctor: ## Sanity-check the host setup
	@scripts/doctor.sh

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
