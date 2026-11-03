"""All experiment constants in one place. Units are SI (m, s, rad) unless the name says otherwise."""
import numpy as np

# --- MEA layout (CL1 default 8x8 array: channel = 8 * column + row) --------------------------
UNUSABLE = {0, 7, 56, 63, 4}                 # four grounded corners + reference channel 4


def channel(row: int, col: int) -> int:
    return 8 * col + row


# Eight rays at 22.5 + 45k degrees counter-clockwise from the heading (k = 0..7), so rays
# 0-3 sweep the left side front to back and rays 4-7 sweep the right side back to front.
# Each ray drives one sensory electrode in the two centre columns: column 3 holds the left
# rays (rows 2-5, front to back) and column 4 the right rays, a coarse top-down map of the view.
SENSORY = [channel(2 + k, 3) for k in range(4)] + [channel(5 - k, 4) for k in range(4)]
# Motor regions: the two outer column pairs. Columns 2 and 5 are an unused buffer that keeps
# stimulation artifacts and direct evoked responses away from the decoded electrodes.
MOTOR_LEFT = [channel(r, c) for c in (0, 1) for r in range(8) if channel(r, c) not in UNUSABLE]
MOTOR_RIGHT = [channel(r, c) for c in (6, 7) for r in range(8) if channel(r, c) not in UNUSABLE]

# --- Rays -------------------------------------------------------------------------------------
RAY_ANGLES = np.deg2rad(22.5 + 45 * np.arange(8))   # relative to heading, counter-clockwise
RAY_MAX_RANGE = 2.0                          # distances beyond this are clipped

# --- Sensory encoding (DishBrain-style rate coding) -------------------------------------------
FREQ_MIN_HZ = 4.0                            # pulse rate for an obstacle at RAY_MAX_RANGE
FREQ_MAX_HZ = 40.0                           # pulse rate for an obstacle touching the agent
SENSORY_UA = 1.0
PULSE_US = 160

# --- Feedback ---------------------------------------------------------------------------------
PREDICTABLE_HZ = 100                         # all sensory electrodes together
PREDICTABLE_PULSES = 10                      # 10 pulses at 100 Hz = 100 ms
PREDICTABLE_UA = 1.0
UNPREDICTABLE_HZ = 5.0                       # mean rate of pulses on random sensory electrodes
UNPREDICTABLE_S = 4.0
UNPREDICTABLE_UA = 2.0
MILESTONE_M = 0.5                            # predictable feedback every 0.5 m of new progress

# --- Motor decoding ---------------------------------------------------------------------------
RATE_TAU_S = 0.1                             # fast spike-rate estimate per motor region
BASELINE_TAU_S = 30.0                        # slow baseline that removes each region's own bias
TURN_GAIN = 6.0                              # applied to the lateralisation index in [-1, 1]
TURN_MAX = 1.5                               # rad/s

# --- Agent and episodes -----------------------------------------------------------------------
TICK_HZ = 100
SPEED = 0.2                                  # constant forward speed
GOAL_RADIUS = 0.3
EPISODE_MAX_S = 60.0
CALIBRATION_S = 10.0                         # spontaneous activity only, before the first episode

# --- Scene preparation ------------------------------------------------------------------------
SCENE_URL = "https://github.com/isl-org/open3d_downloads/releases/download/augmented-icl-nuim/livingroom.ply.zip"
SCENE_MD5 = "841f32ff6294bb52d5f9574834e0925e"
ROOM_X = (-2.70, 2.75)                       # crop to the room interior (scene coordinates)
ROOM_Z = (-2.05, 3.20)
GRID_RES = 0.05
OBSTACLE_BAND = (0.30, 1.20)                 # heights above the lowest floor plane that block the agent
                                             # (the cloud has two floor planes ~0.22 m apart)
AGENT_RADIUS = 0.20
START = (1.85, -1.30, np.pi / 2)             # x, z, heading: bottom-right alcove of the map, facing +z
GOAL = (-0.75, 2.65)                         # far corner, reachable either way round the table

assert not set(SENSORY + MOTOR_LEFT + MOTOR_RIGHT) & UNUSABLE
assert len(set(SENSORY + MOTOR_LEFT + MOTOR_RIGHT)) == len(SENSORY + MOTOR_LEFT + MOTOR_RIGHT)
