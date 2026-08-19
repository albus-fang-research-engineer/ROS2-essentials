# cells/

One `.env` per physical machine. `.env` at the repo root is a symlink into
this directory, created by `make setup` (which uses `hostname` by default).

Cell configs **are** committed. They contain robot IPs and camera serials, not
secrets, and the whole point is that a bench can be rebuilt from git.

Add a machine:

```bash
cp cells/example-ur5e-01.env cells/penn-bench-02.env
$EDITOR cells/penn-bench-02.env      # CELL_NAME, COMPOSE_PROFILES, ROBOT_IP
make setup CELL=penn-bench-02
```
