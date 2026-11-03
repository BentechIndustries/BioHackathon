"""3D navigation: a drone flies through the scanned living room, steered by a linear readout
of an unmodified LIF network (reservoir mode).

    lidar (32 rays: 8 around x 4 tilts) -> rate code (4..max Hz) on electrode columns 2-5
    -> network spreads activity -> firing rates on columns 0,1,6,7 (never stimulated)
    -> ridge readout -> (turn rate, climb rate)

The readout is trained to imitate a rule-based expert; the network itself is never changed.
Writes replay/data.js for replay/index.html.

    uv run --project ../biocompute-outlier-labs python nav3d.py --dry          # world + expert only, no neurons
    CL_SDK_ACCELERATED_TIME=1 uv run --project ../biocompute-outlier-labs python nav3d.py
    uv run --project ../biocompute-outlier-labs python nav3d.py --collect 60 --fly 30   # real time, live SDK viewer
"""
import argparse
import json
import webbrowser
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_dilation, distance_transform_edt, label

import config as C

HERE = Path(__file__).parent

# --- world -------------------------------------------------------------------------------------
RES = 0.05                       # voxel size (m)
CEILING = 1.9                    # the scan stops here; treated as a solid ceiling
RANGE = 2.0                      # lidar range (m), same as the 2D task
R_DRONE = 0.15                   # collision radius
SPEED, TURN_MAX, CLIMB_MAX = 0.4, 1.5, 0.3       # m/s, rad/s, m/s (at 0.2 m/s a constant turn never crashes)
TICK_HZ = 100
DT = 1.0 / TICK_HZ
AZ = C.RAY_ANGLES                # 8 around, CCW from heading: 0-3 left front->back, 4-7 right back->front
EL = np.deg2rad([45, 15, -15, -45])

# --- electrodes (CL1 layout: channel = 8*col + row) ------------------------------------------------
# Tilt -> column: the +-15 deg tilts (obstacles at flying height, what steering needs) sit next to the
# readout columns 1 and 6; +-45 deg (ceiling/floor) sit in the middle.
TILT_COL = [3, 2, 5, 4]          # +45, +15, -15, -45
SENSORY = np.array([[C.channel(k, TILT_COL[t]) for t in range(len(EL))] for k in range(len(AZ))])   # (8 az, 4 el)
READOUT = [C.channel(r, c) for c in (0, 1, 6, 7) for r in range(8) if C.channel(r, c) not in C.UNUSABLE]
LIVE = [c for c in range(64) if c not in C.UNUSABLE]
RATE_TAU = 0.1                   # s, smoothing of per-channel firing rates fed to the readout


class Room:
    """Voxelised ICL-NUIM living room. Coordinates are (x, z, h): floor plane x/z, height h."""

    def __init__(self):
        raw = (HERE / "scene/livingroom_room.ply").read_bytes()
        p = np.frombuffer(raw[raw.index(b"end_header\n") + 11:], "<f8").reshape(-1, 3)[:, [0, 2, 1]].copy()
        p[:, 2] -= np.percentile(p[:, 2], 1)
        self.origin = np.array([C.ROOM_X[0], C.ROOM_Z[0], 0.0])
        self.shape = np.ceil((np.array([C.ROOM_X[1], C.ROOM_Z[1], CEILING]) - self.origin) / RES).astype(int)
        idx = np.floor((p - self.origin) / RES).astype(int)
        keep = np.all((idx >= 0) & (idx < self.shape), axis=1)
        occ = np.zeros(self.shape, bool)
        occ[tuple(idx[keep].T)] = True
        occ = binary_dilation(occ)            # ponytail: closes gaps between scan points, walls +5 cm
        occ[0] = occ[-1] = occ[:, 0] = occ[:, -1] = occ[..., 0] = occ[..., -1] = True
        self.occ = occ
        self.clear = distance_transform_edt(~occ) * RES
        free = self.clear > R_DRONE
        labels, _ = label(free)
        free = labels == np.bincount(labels[free]).argmax()          # largest connected air volume
        self.spawn = np.argwhere(free & (self.clear > 0.4))
        self.points = p[keep]
        self.steps = np.arange(1, int(RANGE / (RES / 2)) + 1) * (RES / 2)

    def cell(self, pts):
        idx = np.floor((pts - self.origin) / RES).astype(int)
        inside = np.all((idx >= 0) & (idx < self.shape), axis=-1)
        idx = np.clip(idx, 0, self.shape - 1)
        return idx[..., 0], idx[..., 1], idx[..., 2], inside

    def blocked(self, pos) -> bool:
        i, j, k, inside = self.cell(np.asarray(pos))
        return bool(~inside or self.clear[i, j, k] < R_DRONE)

    def rays(self, pos, yaw) -> np.ndarray:
        """Distance to the first solid voxel along each ray, (8 az, 4 el), capped at RANGE."""
        a, e = np.meshgrid(yaw + AZ, EL, indexing="ij")
        d = np.stack([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)], -1).reshape(-1, 3)
        i, j, k, inside = self.cell(pos + self.steps[:, None, None] * d[None])
        hit = self.occ[i, j, k] | ~inside
        first = np.where(hit.any(0), hit.argmax(0), len(self.steps) - 1)
        return self.steps[first].reshape(len(AZ), len(EL))


class Drone:
    def __init__(self, room: Room, rng: np.random.Generator):
        self.room, self.rng = room, rng
        self.reset()

    def reset(self):
        cell = self.room.spawn[self.rng.integers(len(self.room.spawn))]
        self.pos = self.room.origin + (cell + 0.5) * RES
        self.yaw = self.rng.uniform(0, 2 * np.pi)

    def step(self, turn, climb) -> bool:
        """Fly one tick. On collision, respawn and return True."""
        turn, climb = np.clip(turn, -TURN_MAX, TURN_MAX), np.clip(climb, -CLIMB_MAX, CLIMB_MAX)
        self.yaw = (self.yaw + turn * DT) % (2 * np.pi)
        self.pos = self.pos + DT * np.array([SPEED * np.cos(self.yaw), SPEED * np.sin(self.yaw), climb])
        if self.room.blocked(self.pos):
            self.reset()
            return True
        return False


FRONT_W = np.array([1.0, 0.6, 0.3, 0.1])          # weight of rays front -> back on each side


def expert(dist) -> np.ndarray:
    """Teacher, using only the rays (so a readout can learn it): (turn, climb)."""
    p = 1.0 - dist / RANGE
    level = p[:, 1:3].mean(1)                     # the +-15 deg tilts see obstacles at flying height
    left, right = FRONT_W @ level[[0, 1, 2, 3]], FRONT_W @ level[[7, 6, 5, 4]]
    diff = right - left                           # > 0: right side closer -> turn left (CCW, positive)
    front = level[[0, 7]].max()
    turn = TURN_MAX * np.tanh(3 * diff + 3 * front ** 2 * np.sign(diff + 1e-3))
    ahead = p[[0, 7, 1, 6]]
    climb = CLIMB_MAX * np.tanh(4 * (ahead[:, 2:].mean() - ahead[:, :2].mean()))
    return np.array([turn, climb])


class Noise:
    """Smoothed random steering (Ornstein-Uhlenbeck), so training visits near-miss states."""

    def __init__(self, rng, scale):
        self.rng, self.scale, self.x = rng, np.asarray(scale), np.zeros(2)

    def __call__(self):
        self.x += -self.x * DT / 0.5 + self.scale * np.sqrt(2 * DT / 0.5) * self.rng.standard_normal(2)
        return self.x


class Encoder:
    """run.Encoder extended to 32 rays: distance -> pulse rate, one phase accumulator per ray."""

    def __init__(self, rng, max_hz):
        self.phase, self.max_hz = rng.random(SENSORY.size), max_hz

    def due(self, dist) -> np.ndarray:
        close = 1.0 - np.clip(dist.ravel() / RANGE, 0.0, 1.0)
        self.phase += (C.FREQ_MIN_HZ + (self.max_hz - C.FREQ_MIN_HZ) * close) * DT
        fire = self.phase >= 1.0
        self.phase[fire] -= 1.0
        return SENSORY.ravel()[fire]


def fit(X, Y, lam=10.0):
    """Ridge regression on z-scored features. Returns (predict, per-feature weights in raw units)."""
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Z = np.c_[(X - mu) / sd, np.ones(len(X))]
    W = np.linalg.solve(Z.T @ Z + lam * np.eye(Z.shape[1]), Z.T @ Y)
    return (lambda x: np.r_[(x - mu) / sd, 1.0] @ W), W[:-1] / sd[:, None]


def r2(pred, Y):
    return 1 - ((Y - pred) ** 2).sum(0) / ((Y - Y.mean(0)) ** 2).sum(0)


def cv_r2(X, Y, k=5):
    """R^2 over k contiguous held-out blocks (one held-out block alone can be an unseen part of the room)."""
    edges, pred = np.linspace(0, len(Y), k + 1).astype(int), np.zeros_like(Y)
    for a, b in zip(edges[:-1], edges[1:]):
        f, _ = fit(np.r_[X[:a], X[b:]], np.r_[Y[:a], Y[b:]])
        pred[a:b] = [f(x) for x in X[a:b]]
    return r2(pred, Y)


# --- logging for the replay ----------------------------------------------------------------------
class Log:
    EVERY = 5                                     # one frame per 5 ticks = 20 fps

    def __init__(self):
        self.frames, self.phases, self.stim, self.spk, self.n = [], [], set(), [], 0

    def phase(self, name):
        self.phases.append({"name": name, "start": len(self.frames)})

    def tick(self, drone, dist, stim, spikes, cmd, target, crashed):
        self.stim.update(int(c) for c in stim)
        self.spk.extend(int(c) for c in spikes)
        self.n += 1
        if crashed or self.n % self.EVERY == 0:
            self.frames.append({"p": np.round(drone.pos, 3).tolist(), "yaw": round(float(drone.yaw), 3),
                                "rays": np.round(dist.ravel(), 2).tolist(), "stim": sorted(self.stim),
                                "spk": sorted(self.spk), "cmd": np.round(cmd, 3).tolist(),
                                "exp": np.round(target, 3).tolist(), "crash": bool(crashed)})
            self.stim, self.spk = set(), []       # spk keeps repeats: one entry per spike


# --- flying --------------------------------------------------------------------------------------
def fly_offline(room, seconds, policy, seed):
    drone, crashes = Drone(room, np.random.default_rng(seed)), 0
    for _ in range(int(seconds * TICK_HZ)):
        crashes += drone.step(*policy(room.rays(drone.pos, drone.yaw)))
    return crashes


def fly_neural(neurons, room, seconds, controller, seed, max_hz, log, noise=None, save=None):
    """controller(rate64, dist) -> (turn, climb). Returns rates, ray proximities, expert targets, crashes."""
    import cl
    pulse = cl.StimDesign(200, -1.5, 200, 1.5)    # well above the LIF firing threshold (~0.8 uA)
    rng = np.random.default_rng(seed)
    drone, enc, rate = Drone(room, rng), Encoder(rng, max_hz), np.zeros(64)
    rates, prox, targets, counts, crashes = [], [], [], [], 0
    for tick in neurons.loop(TICK_HZ, stop_after_seconds=seconds):
        spikes = [s.channel for s in tick.analysis.spikes]
        counts.append(np.bincount(spikes, minlength=64))
        rate += DT / RATE_TAU * (counts[-1] / DT - rate)
        dist = room.rays(drone.pos, drone.yaw)
        due = enc.due(dist)
        if len(due):
            neurons.stim(cl.ChannelSet(*due.tolist()), pulse)
        target = expert(dist)
        cmd = controller(rate, dist) + (noise() if noise else 0)
        rates.append(rate.copy()); prox.append(1 - dist.ravel() / RANGE); targets.append(target)
        crashed = drone.step(*cmd)
        crashes += crashed
        log.tick(drone, dist, due, spikes, cmd, target, crashed)
    if save:                                          # raw per-tick data for offline analysis
        np.savez_compressed(save, counts=np.array(counts), prox=np.array(prox), targets=np.array(targets))
    return np.array(rates), np.array(prox), np.array(targets), crashes


def score(name, crashes, seconds):
    print(f"  {name:<30} {crashes:4d} crashes in {seconds:g} s   "
          f"{crashes / seconds * 60:5.1f}/min   {SPEED * seconds / max(crashes, 1):5.1f} m per crash")


def selfcheck(room):
    assert len(room.spawn) > 100, "no room to spawn"
    d = room.rays(room.origin + (room.spawn[0] + 0.5) * RES, 0.0)
    assert d.shape == (8, 4) and np.all((d > 0) & (d <= RANGE))
    assert abs(expert(np.full((8, 4), RANGE))).max() < 1e-2      # nothing in range -> fly straight
    assert SENSORY.size == 32 and len(READOUT) == 27 and not set(SENSORY.ravel()) & (set(READOUT) | C.UNUSABLE)


def main():
    global SPEED
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collect", type=float, default=180, help="seconds of expert flight to train on")
    ap.add_argument("--fly", type=float, default=90, help="seconds of test flight per controller")
    ap.add_argument("--coupling", type=float, default=4.0, help="LIF coupling_gain_mV")
    ap.add_argument("--max-hz", type=float, default=100.0, help="pulse rate for an obstacle touching the drone")
    ap.add_argument("--speed", type=float, default=SPEED, help="forward speed (m/s); faster = harder")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry", action="store_true", help="world + expert/random baselines only, no neurons")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    SPEED = args.speed

    room = Room()
    selfcheck(room)
    test_seed = args.seed + 1
    rnd = Noise(np.random.default_rng(0), [TURN_MAX, CLIMB_MAX])
    if args.dry:
        print(f"Room {room.shape} voxels, {len(room.spawn)} spawn cells. Baselines, {args.fly:g} s each:")
        score("expert (ceiling)", fly_offline(room, args.fly, expert, test_seed), args.fly)
        score("random steering (floor)", fly_offline(room, args.fly, lambda d: rnd(), test_seed), args.fly)
        score("constant gentle turn", fly_offline(room, args.fly, lambda d: np.array([0.15, 0.0]), test_seed), args.fly)
        return

    import cl
    from organoid_simulator.lif_data_source import small_world_connectivity
    if cl.is_simulator():
        cl.sim.set_simulator_data_source("organoid_simulator.lif_data_source:make_lif_source",
                                         config={"random_seed": args.seed, "coupling_gain_mV": args.coupling})
    log = Log()
    with cl.open() as neurons:
        server = getattr(neurons, "_websocket_server", None)
        if server is not None and not args.no_browser:
            webbrowser.open(server.web_url)

        print(f"1. Collecting {args.collect:g} s of expert flight (with steering noise) ...")
        log.phase("collect: expert + noise")
        noise = Noise(np.random.default_rng(args.seed), [0.8, 0.15])
        X, P, Y, _ = fly_neural(neurons, room, args.collect, lambda r, d: expert(d), args.seed,
                                args.max_hz, log, noise, save=HERE / "replay/collect.npz")

        feats = {"raw rays (no neurons)": P, "neurons: readout cols (27)": X[:, READOUT],
                 "neurons: all live (59)": X[:, LIVE]}
        print(f"\n2. Readout fit, 5-block cross-validated R^2 (turn, climb):")
        models = {}
        for name, F in feats.items():
            print(f"  {name:<30} {np.round(cv_r2(F, Y), 2)}")
            models[name] = fit(F, Y)                  # refit on everything for flying

        print(f"\n3. Test flights, {args.fly:g} s each (same spawns):")
        for name, cols in [("neurons: readout cols (27)", READOUT), ("neurons: all live (59)", LIVE)]:
            log.phase(f"fly: {name}")
            pred = models[name][0]
            _, _, _, crashes = fly_neural(neurons, room, args.fly, lambda r, d, pred=pred, cols=cols: pred(r[cols]),
                                          test_seed, args.max_hz, log)
            score(name, crashes, args.fly)
    raw = models["raw rays (no neurons)"][0]
    score("raw-ray readout", fly_offline(room, args.fly, lambda d: raw(1 - d.ravel() / RANGE), test_seed), args.fly)
    score("expert (ceiling)", fly_offline(room, args.fly, expert, test_seed), args.fly)
    score("random steering (floor)", fly_offline(room, args.fly, lambda d: rnd(), test_seed), args.fly)
    mean_cmd = Y.mean(0)
    score("constant (mean) command", fly_offline(room, args.fly, lambda d: mean_cmd, test_seed), args.fly)

    A = small_world_connectivity()                # same defaults/seed as the simulator's wiring
    turn_w = np.zeros(64)
    turn_w[READOUT] = models["neurons: readout cols (27)"][1][:, 0]
    # full cloud; the page thins it while rotating
    data = {"points": np.round(room.points, 2).tolist(), "origin": room.origin.tolist(),
            "size": (room.shape * RES).tolist(), "range": RANGE, "az": AZ.tolist(), "el": EL.tolist(),
            "sensory": SENSORY.ravel().tolist(), "readout": READOUT, "dead": sorted(C.UNUSABLE),
            "edges": [[int(j), int(i), round(float(A[i, j]), 3)] for i, j in zip(*np.nonzero(A))],
            "turn_w": np.round(turn_w, 4).tolist(), "fps": TICK_HZ / Log.EVERY,
            "phases": log.phases, "frames": log.frames}
    out = HERE / "replay/data.js"
    out.write_text("window.RUN = " + json.dumps(data, separators=(",", ":")) + ";\n")
    print(f"\nReplay: open {HERE / 'replay/index.html'}  ({len(log.frames)} frames)")


if __name__ == "__main__":
    main()
