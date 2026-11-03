"""The simulated body: a disc-shaped agent with eight range rays, driving through the room map."""
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import config as C


@dataclass
class Scene:
    occ: np.ndarray          # True where something 30-120 cm tall blocks the floor
    free: np.ndarray         # True where the agent's centre may be (obstacles padded by its radius)
    dist: np.ndarray         # geodesic distance to the goal in metres (inf outside `free`)
    origin: np.ndarray       # (x, z) of the grid corner
    res: float
    start: np.ndarray        # (x, z, heading)
    goal: np.ndarray         # (x, z)

    @classmethod
    def load(cls, path: Path) -> "Scene":
        with np.load(path) as f:
            return cls(**{k: f[k] for k in ("occ", "free", "dist", "origin", "start", "goal")}, res=float(f["res"]))

    def cells(self, x: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        rows = np.floor((z - self.origin[1]) / self.res).astype(int)
        cols = np.floor((x - self.origin[0]) / self.res).astype(int)
        inside = (rows >= 0) & (rows < self.occ.shape[0]) & (cols >= 0) & (cols < self.occ.shape[1])
        return np.clip(rows, 0, self.occ.shape[0] - 1), np.clip(cols, 0, self.occ.shape[1] - 1), inside

    def is_free(self, x: float, z: float) -> bool:
        r, c, inside = self.cells(np.array(x), np.array(z))
        return bool(inside and self.free[r, c])

    def geodesic(self, x: float, z: float) -> float:
        r, c, _ = self.cells(np.array(x), np.array(z))
        return float(self.dist[r, c])

    def rays(self, x: float, z: float, heading: float) -> np.ndarray:
        """Distance (m) along each ray to the first obstacle cell, clipped at RAY_MAX_RANGE."""
        steps = np.arange(1, int(C.RAY_MAX_RANGE / (self.res / 2)) + 1) * (self.res / 2)
        angles = heading + C.RAY_ANGLES
        px = x + steps[:, None] * np.cos(angles)[None, :]
        pz = z + steps[:, None] * np.sin(angles)[None, :]
        r, c, inside = self.cells(px, pz)
        hit = self.occ[r, c] | ~inside
        first = np.where(hit.any(axis=0), hit.argmax(axis=0), len(steps) - 1)
        return steps[first]


class Agent:
    """Constant forward speed; the culture only chooses the turn rate."""

    def __init__(self, scene: Scene, rng: np.random.Generator):
        self.scene, self.rng = scene, rng
        self.reset()

    def reset(self) -> None:
        x, z, heading = self.scene.start
        self.x, self.z = float(x), float(z)
        self.heading = float(heading) + self.rng.uniform(-np.pi / 8, np.pi / 8)
        self.start_dist = self.best_dist = self.scene.geodesic(self.x, self.z)

    def step(self, turn_rate: float, dt: float) -> str | None:
        """Advance one tick. Returns 'collision', 'goal' or None."""
        self.heading = (self.heading + turn_rate * dt) % (2 * np.pi)
        x = self.x + C.SPEED * dt * np.cos(self.heading)
        z = self.z + C.SPEED * dt * np.sin(self.heading)
        if not self.scene.is_free(x, z):
            return "collision"
        self.x, self.z = x, z
        if np.hypot(x - self.scene.goal[0], z - self.scene.goal[1]) < C.GOAL_RADIUS:
            return "goal"
        return None

    @property
    def progress(self) -> float:
        """Fraction of the start-to-goal geodesic distance covered (can be negative)."""
        return 1.0 - self.scene.geodesic(self.x, self.z) / self.start_dist
