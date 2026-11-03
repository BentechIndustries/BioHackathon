import queue
import random
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cl
from cl import ChannelSet, StimDesign

from .cube import Cube, move_name

TICKS_PER_SECOND = 10
TICKS_PER_BEAT = 10
MOVE_CHANNELS = (
    (8, 9, 10, 11),
    (12, 13, 14, 15),
    (16, 17, 18, 19),
    (20, 21, 22, 23),
    (24, 25, 26, 27),
    (28, 29, 30, 31),
    (32, 33, 34, 35),
    (36, 37, 38, 39),
    (40, 41, 42, 43),
    (44, 45, 46, 47),
    (48, 49, 50, 51),
    (52, 53, 54, 55),
)
_CHANNEL_MOVE = {}
for _move, _channels in enumerate(MOVE_CHANNELS):
    for _channel in _channels:
        _CHANNEL_MOVE[_channel] = _move

_REWARD = StimDesign(160, -1.0, 160, 1.0)
_FACE_WORDS = {
    "U": "top face",
    "D": "bottom face",
    "L": "left face",
    "R": "right face",
    "F": "front face",
    "B": "back face",
}


def plain_turn(move):
    name = move if isinstance(move, str) else move_name(move)
    if not name:
        return ""
    face = _FACE_WORDS[name[0]]
    if name.endswith("'"):
        return f"{face}, counterclockwise"
    return f"{face}, clockwise"


def _start_controls(commands):
    class Handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self):
            self._send(204)

        def do_POST(self):
            action = self.path.strip("/")
            if action in ("mix", "done"):
                commands.put(action)
            self._send(204)

        def _send(self, code):
            self.send_response(code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def _take_commands(commands):
    found = []
    while True:
        try:
            found.append(commands.get_nowait())
        except queue.Empty:
            return found


def play(duration_s, seed=None, commands=None):
    rng = random.Random(seed)
    cube = Cube()
    scramble = []
    last_face = None
    accepted = []
    listen_ticks = int(duration_s * TICKS_PER_SECOND)
    own_server = None
    if commands is None:
        commands = queue.Queue()
        own_server, control_url = _start_controls(commands)
    else:
        control_url = ""
    try:
        return _play(duration_s, rng, cube, scramble, last_face, accepted, listen_ticks, commands, control_url)
    finally:
        if own_server is not None:
            own_server.shutdown()


def _play(duration_s, rng, cube, scramble, last_face, accepted, listen_ticks, commands, control_url):
    controls = "mix"
    with cl.open() as neurons:
        stream = neurons.create_data_stream("cube")
        stamp = -1

        def publish(when, move_code, label, detail, note, needed, loudest):
            nonlocal stamp
            when = int(when)
            if when <= stamp:
                when = stamp + 1
            stamp = when
            stream.append(
                stamp,
                {
                    "facelets": list(cube.facelets),
                    "move": move_code,
                    "label": label,
                    "detail": detail,
                    "note": note,
                    "needed": needed,
                    "loudest": loudest,
                    "solved": label == "The cube is solved",
                    "turns": len(accepted),
                    "control_url": control_url,
                    "controls": controls,
                },
            )

        mixed = None
        remaining = []
        solving = False
        solve_from = None
        hold_until = -1
        last_detail = "The cube is solved."
        announced = False
        for tick in neurons.loop(
            ticks_per_second=TICKS_PER_SECOND,
            stop_after_seconds=duration_s + 900,
            ignore_jitter=True,
        ):
            when = tick.iteration_next_timestamp
            if not solving:
                if not announced:
                    publish(when, "", "Press Mix", "Each click turns one face.", "Then press Done mixing.", "", "")
                    announced = True
                for action in _take_commands(commands):
                    if action == "mix":
                        choices = [move for move in range(12) if move // 2 != last_face]
                        move = rng.choice(choices)
                        cube.apply(move)
                        scramble.append(move)
                        last_face = move // 2
                        last_detail = plain_turn(move)
                        publish(when, move_name(move), "You mixed it", last_detail, "Mix again, or press Done mixing.", "", "")
                    elif action == "done":
                        if cube.solved():
                            if scramble:
                                publish(when, "", "The cube is solved", "The mix came back to solved.", "Press Mix if you want to mix again.", "", "")
                                scramble.clear()
                                last_face = None
                            else:
                                publish(when, "", "Press Mix", "The cube is still solved.", "Turn it at least once, then press Done mixing.", "", "")
                        else:
                            mixed = cube.net()
                            remaining = cube.solution()
                            solving = True
                            solve_from = tick.iteration
                            controls = "off"
                            break
                if not solving:
                    continue
            if solve_from is not None and tick.iteration - solve_from >= listen_ticks:
                tick.loop.stop()
                break
            if not remaining:
                publish(when, "", "The cube is solved", "Every face is one color.", f"Turns from the dish: {len(accepted)}.", "", "")
                tick.loop.stop()
                break
            if tick.iteration < hold_until:
                needed_code = move_name(remaining[0])
                publish(when, "", "The dish turned it", last_detail, "Blue spots are the reward.", needed_code, needed_code)
                continue
            counts = [0] * 12
            for spike in tick.analysis.spikes:
                move = _CHANNEL_MOVE.get(spike.channel)
                if move is not None:
                    counts[move] += 1
            top = max(counts)
            winners = [move for move, count in enumerate(counts) if count == top and count > 0]
            needed = remaining[0]
            needed_code = move_name(needed)
            loudest = winners[0] if len(winners) == 1 else None
            if loudest == needed:
                cube.apply(needed)
                accepted.append(needed)
                remaining = remaining[1:]
                last_detail = plain_turn(needed)
                if not remaining:
                    publish(when, needed_code, "The cube is solved", last_detail, "The dish made the last turn.", "", "")
                    neurons.stim(ChannelSet(*MOVE_CHANNELS[needed]), _REWARD)
                    tick.loop.stop()
                    break
                publish(when, needed_code, "The dish turned it", last_detail, "Blue spots are the reward.", move_name(remaining[0]), needed_code)
                neurons.stim(ChannelSet(*MOVE_CHANNELS[needed]), _REWARD)
                hold_until = tick.iteration + TICKS_PER_BEAT
                continue
            if loudest is None and top > 0:
                note = "Several groups are tied, so no turn is taken."
                loud_code = ""
            elif loudest is None:
                note = "The dish is quiet, so the cube stays still."
                loud_code = ""
            else:
                note = f"Loudest is {plain_turn(loudest)}. That is not the next turn."
                loud_code = move_name(loudest)
            publish(when, "", "Waiting for the dish", f"Next turn: {plain_turn(needed)}.", note, needed_code, loud_code)
        if mixed is None:
            mixed = cube.net()
    solved = cube.solved()
    outcome = "Solved." if solved else "Time ran out before it was solved."
    text = "\n".join(
        [
            outcome,
            "",
            "Your mix:",
            ", ".join(plain_turn(move) for move in scramble),
            "",
            "Mixed cube:",
            mixed,
            "",
            "Turns the dish made:",
            ", ".join(plain_turn(move) for move in accepted) if accepted else "none",
            "",
            "Cube now:",
            cube.net(),
        ]
    )
    return solved, text
