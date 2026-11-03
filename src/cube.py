FACES = ("U", "R", "F", "D", "L", "B")
MOVE_NAMES = tuple(f"{face}{suffix}" for face in FACES for suffix in ("", "'"))
SOLVED = tuple(i // 4 for i in range(24))
_FACE_OF = {name: index for index, name in enumerate("URFDLB")}

_CORNERS = (
    ((-1, 1, -1), (("U", 0), ("B", 21), ("L", 16))),
    ((1, 1, -1), (("U", 1), ("R", 5), ("B", 20))),
    ((-1, 1, 1), (("U", 2), ("L", 17), ("F", 8))),
    ((1, 1, 1), (("U", 3), ("F", 9), ("R", 4))),
    ((-1, -1, 1), (("D", 12), ("F", 10), ("L", 19))),
    ((1, -1, 1), (("D", 13), ("R", 6), ("F", 11))),
    ((-1, -1, -1), (("D", 14), ("L", 18), ("B", 23))),
    ((1, -1, -1), (("D", 15), ("B", 22), ("R", 7))),
)

_NORMALS = {
    "U": (0, 1, 0),
    "D": (0, -1, 0),
    "R": (1, 0, 0),
    "L": (-1, 0, 0),
    "F": (0, 0, 1),
    "B": (0, 0, -1),
}


def _rot_u(x, y, z):
    return (-z, y, x)


def _rot_r(x, y, z):
    return (x, z, -y)


def _rot_f(x, y, z):
    return (y, -x, z)


def _rot_d(x, y, z):
    return (z, y, -x)


def _rot_l(x, y, z):
    return (x, -z, y)


def _rot_b(x, y, z):
    return (-y, x, z)


_ROTS = {
    "U": _rot_u,
    "R": _rot_r,
    "F": _rot_f,
    "D": _rot_d,
    "L": _rot_l,
    "B": _rot_b,
}

_SLOTS = {}
for coord, stickers in _CORNERS:
    for name, index in stickers:
        _SLOTS[(coord, _NORMALS[name])] = index


def _perm_for(face):
    rot = _ROTS[face]
    normal = _NORMALS[face]
    source_of = list(range(24))
    for coord, stickers in _CORNERS:
        if sum(a * b for a, b in zip(coord, normal)) <= 0:
            continue
        dest = rot(*coord)
        for name, index in stickers:
            turned = rot(*_NORMALS[name])
            source_of[_SLOTS[(dest, turned)]] = index
    return tuple(source_of)


_PERMS = []
for _face in FACES:
    clockwise = _perm_for(_face)
    _PERMS.append(clockwise)
    _PERMS.append(tuple(clockwise[clockwise[clockwise[i]]] for i in range(24)))


def _apply(state, move):
    perm = _PERMS[move]
    return tuple(state[perm[i]] for i in range(24))


def inverse(move):
    return move ^ 1


class Cube:
    def __init__(self, facelets=SOLVED):
        self.facelets = tuple(facelets)

    def apply(self, move):
        self.facelets = _apply(self.facelets, move)
        return self

    def solved(self):
        return self.facelets == SOLVED

    def scramble(self, turns, rng):
        used = []
        last_face = None
        for _ in range(turns):
            choices = [move for move in range(12) if move // 2 != last_face]
            move = rng.choice(choices)
            self.apply(move)
            used.append(move)
            last_face = move // 2
        return used

    def solution(self):
        return solve(self.facelets)

    def net(self):
        letters = "WRGYOB"
        cell = [letters[color] for color in self.facelets]

        def row(a, b):
            return f"{cell[a]} {cell[b]}"

        blank = "    "
        return "\n".join(
            [
                f"{blank}{row(0, 1)}",
                f"{blank}{row(2, 3)}",
                f"{row(16, 17)} {row(8, 9)} {row(4, 5)} {row(20, 21)}",
                f"{row(18, 19)} {row(10, 11)} {row(6, 7)} {row(22, 23)}",
                f"{blank}{row(12, 13)}",
                f"{blank}{row(14, 15)}",
            ]
        )


def solve(start):
    start = tuple(start)
    if start == SOLVED:
        return []
    forward_parent = {start: (None, None)}
    backward_parent = {SOLVED: (None, None)}
    forward_queue = [start]
    backward_queue = [SOLVED]
    meeting = None
    while forward_queue and backward_queue and meeting is None:
        if len(forward_parent) <= len(backward_parent):
            meeting = _expand(forward_queue, forward_parent, backward_parent)
        else:
            meeting = _expand(backward_queue, backward_parent, forward_parent)
    if meeting is None:
        raise RuntimeError("cube position has no solution")
    prefix = []
    node = meeting
    while forward_parent[node][0] is not None:
        previous, move = forward_parent[node]
        prefix.append(move)
        node = previous
    prefix.reverse()
    suffix = []
    node = meeting
    while backward_parent[node][0] is not None:
        previous, move = backward_parent[node]
        suffix.append(inverse(move))
        node = previous
    return prefix + suffix


def _expand(queue, parent, other):
    current = queue
    found = None
    nxt_queue = []
    for state in current:
        for move in range(12):
            child = _apply(state, move)
            if child in parent:
                continue
            parent[child] = (state, move)
            if child in other:
                found = child
                break
            nxt_queue.append(child)
        if found is not None:
            break
    queue[:] = nxt_queue
    return found


def move_name(move):
    return MOVE_NAMES[move]


def sequence_text(moves):
    if not moves:
        return "already solved"
    return " ".join(move_name(move) for move in moves)
