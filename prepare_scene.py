"""Download the ICL-NUIM living room point cloud and turn it into a 2D navigation map.

    python prepare_scene.py --out scene

Writes scene/livingroom.npz (obstacle grid, drivable grid, geodesic distance to the goal,
start and goal) and scene/livingroom_map.png (a preview). Only needs to run once, on a laptop.
"""
import argparse
import hashlib
import heapq
import io
import urllib.request
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from plyfile import PlyData
from scipy.ndimage import binary_closing, distance_transform_edt, label

import config as C


def download_points() -> np.ndarray:
    blob = urllib.request.urlopen(C.SCENE_URL).read()
    digest = hashlib.md5(blob).hexdigest()
    assert digest == C.SCENE_MD5, f"checksum mismatch: {digest}"
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        vertex = PlyData.read(io.BytesIO(zf.read("livingroom.ply")))["vertex"]
    return np.c_[vertex["x"], vertex["y"], vertex["z"]].astype(np.float64)   # y is up


def build_grids(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x, y, z = points.T
    keep = (x > C.ROOM_X[0]) & (x < C.ROOM_X[1]) & (z > C.ROOM_Z[0]) & (z < C.ROOM_Z[1])
    x, y, z = x[keep], y[keep], z[keep]
    height = y - np.percentile(y, 1)
    origin = np.array([C.ROOM_X[0], C.ROOM_Z[0]])
    shape = (int(np.ceil((C.ROOM_Z[1] - C.ROOM_Z[0]) / C.GRID_RES)),
             int(np.ceil((C.ROOM_X[1] - C.ROOM_X[0]) / C.GRID_RES)))
    rows = ((z - origin[1]) / C.GRID_RES).astype(int)
    cols = ((x - origin[0]) / C.GRID_RES).astype(int)

    def occupancy(mask: np.ndarray) -> np.ndarray:
        grid = np.zeros(shape, bool)
        grid[rows[mask], cols[mask]] = True
        return grid

    occ = binary_closing(occupancy((height > C.OBSTACLE_BAND[0]) & (height < C.OBSTACLE_BAND[1])))
    floor = binary_closing(occupancy(height < C.OBSTACLE_BAND[0]), iterations=3)
    clearance = distance_transform_edt(~occ) * C.GRID_RES
    free = floor & (clearance > C.AGENT_RADIUS)
    labels, _ = label(free)
    free = labels == np.bincount(labels[free]).argmax()          # largest connected region
    return occ, free, origin


def geodesic_distance(free: np.ndarray, goal: tuple[int, int]) -> np.ndarray:
    """Shortest 8-connected path length (m) from every drivable cell to the goal cell."""
    dist = np.full(free.shape, np.inf)
    dist[goal] = 0.0
    queue = [(0.0, goal)]
    steps = [(dr, dc, np.hypot(dr, dc) * C.GRID_RES) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]
    while queue:
        d, (r, c) = heapq.heappop(queue)
        if d > dist[r, c]:
            continue
        for dr, dc, step in steps:
            nr, nc = r + dr, c + dc
            if 0 <= nr < free.shape[0] and 0 <= nc < free.shape[1] and free[nr, nc] and d + step < dist[nr, nc]:
                dist[nr, nc] = d + step
                heapq.heappush(queue, (d + step, (nr, nc)))
    return dist


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path("scene"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    points = download_points()
    occ, free, origin = build_grids(points)
    cell = lambda x, z: (int((z - origin[1]) / C.GRID_RES), int((x - origin[0]) / C.GRID_RES))
    start_cell, goal_cell = cell(*C.START[:2]), cell(*C.GOAL)
    assert free[start_cell], f"START {C.START} is not on drivable floor"
    assert free[goal_cell], f"GOAL {C.GOAL} is not on drivable floor"
    dist = geodesic_distance(free, goal_cell)
    assert np.isfinite(dist[start_cell]), "goal is unreachable from the start"
    np.savez_compressed(args.out / "livingroom.npz", occ=occ, free=free, dist=dist, origin=origin,
                        res=C.GRID_RES, start=np.array(C.START), goal=np.array(C.GOAL))

    fig = plt.figure(figsize=(13, 6))
    ax = fig.add_subplot(1, 2, 1, projection="3d")
    x, y, z = points.T
    y = y - y.min()
    show = (x > C.ROOM_X[0]) & (x < C.ROOM_X[1]) & (z > C.ROOM_Z[0]) & (z < C.ROOM_Z[1]) & (y < 1.9)
    show = np.flatnonzero(show)[::max(show.sum() // 80_000, 1)]
    ax.scatter(x[show], z[show], y[show], c=y[show], cmap="viridis", s=0.3)
    ax.view_init(elev=38, azim=-62)
    ax.set_box_aspect((np.ptp(C.ROOM_X), np.ptp(C.ROOM_Z), 1.9))
    ax.set_axis_off()
    ax.set_title("ICL-NUIM living room point cloud (ceiling removed, colour = height)")
    ax = fig.add_subplot(1, 2, 2)
    ax.imshow(np.where(occ, 0.0, np.where(free, 1.0, 0.75)), origin="lower", cmap="gray", vmin=0, vmax=1,
              extent=[*C.ROOM_X, *C.ROOM_Z])
    ax.contour(np.where(free, dist, np.nan), levels=np.arange(0.5, 10, 0.5), extent=[*C.ROOM_X, *C.ROOM_Z],
               cmap="viridis", linewidths=0.6)
    ax.plot(*C.START[:2], "s", color="tab:green", ms=10, label="start")
    ax.plot(*C.GOAL, "*", color="gold", mec="k", ms=16, label="goal")
    ax.set(xlabel="x (m)", ylabel="z (m)",
           title=f"Obstacles (black), drivable floor (white)\ngeodesic distance contours every 0.5 m; start-goal {dist[start_cell]:.1f} m")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(args.out / "livingroom_map.png", dpi=150)
    print(f"grid {free.shape}, drivable {free.sum() * C.GRID_RES ** 2:.1f} m^2, "
          f"start-goal geodesic {dist[start_cell]:.2f} m -> {args.out}")


if __name__ == "__main__":
    main()
