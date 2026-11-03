# cl-nav: a neuronal culture steering an agent through a 3D-scanned living room

A closed-loop experiment for the Cortical Labs CL1. Eight range rays cast from an agent in the
ICL-NUIM living room are rate-coded onto eight electrodes; spikes in two motor regions turn it
left or right; reaching milestones and the goal earns predictable stimulation, and collisions
earn unpredictable stimulation (after DishBrain, Kagan et al. 2022). Full write-up in
`docs/report.pdf`.

```
python3.12 -m venv .venv && . .venv/bin/activate      # cl-sdk needs Python >= 3.12
pip install -r requirements.txt

python prepare_scene.py                                # once: downloads the room, writes scene/
python run.py --condition feedback --minutes 20        # on the CL1 (or real-time simulator)
python analyze.py recordings/*.h5                      # summary table + figures/sessions.png
```

Testing on a laptop with the simulator:

```
CL_SDK_ACCELERATED_TIME=1 python run.py --toy avoider --minutes 10   # positive control: should avoid walls
CL_SDK_ACCELERATED_TIME=1 python run.py --toy local --minutes 10     # null: responses never reach motor regions
```

`session.ipynb` shows the same session with a live top-down view (`visualiser/`), which needs
real time (no `CL_SDK_ACCELERATED_TIME`).

| file | what it does |
|---|---|
| `config.py` | every constant: electrode layout, encoding, feedback, agent, scene |
| `prepare_scene.py` | point cloud → obstacle grid, drivable grid, geodesic distance to the goal |
| `world.py` | scene lookup, ray casting, agent kinematics |
| `run.py` | the closed loop: encoder, decoder, feedback state machine, logging |
| `culture.py` | simulator-only toy culture with evoked responses (test fixture) |
| `analyze.py` | per-session and per-condition statistics, figure |
| `visualiser/` | live view for the CL data-stream visualiser |

In accelerated mode the simulator gives its data producer only 100 ms per tick; on a busy
machine this can raise `TimeoutError: Timeout waiting for timestamp …`. Rerun with nothing else
running, or drop `CL_SDK_ACCELERATED_TIME`.
