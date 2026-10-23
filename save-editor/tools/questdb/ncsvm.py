"""Path-by-path symbolic interpreter for KotOR NCS bytecode.

Origin: the instruction decoding comes from the research scratchpad's ncsscan.py
(2026-10-22, validated there against the NSS sources in scripts.bif). That scanner
walked each instruction once and merged all branches. This version runs every path
separately (it forks at JZ/JNZ), keeps JSR/RETN on a real return stack, tracks BP for
globals, and records for each finished path:

  conds  the branch conditions taken, as (value, True/False)
  calls  the engine calls made, in order, as (routine name, args, deferred)
  ret    the value left in the return slot (for StartingConditional scripts)

Values are symbolic: Python int/float/str for constants, and tuples for the rest:
  ("call", name, args)   result of an engine routine
  ("op", sym, a, b)      binary operation
  ("not", a) ("neg", a) ("comp", a)
  ("obj", "OBJECT_SELF" | "OBJECT_INVALID")
  ("unk", label)

Calls inside DelayCommand/AssignCommand/ActionDoCommand blocks (STORE_STATE) are
run in place and marked deferred=True.

NCS facts used (big-endian operands, code from offset 13): see the scratchpad's
quest-scripts-research.md, section 1.
"""
import struct

OPS = {0x06: "&&", 0x07: "||", 0x08: "|", 0x09: "^", 0x0A: "&", 0x0B: "==", 0x0C: "!=",
       0x0D: ">=", 0x0E: ">", 0x0F: "<", 0x10: "<=", 0x11: "<<", 0x12: ">>", 0x13: ">>>",
       0x14: "+", 0x15: "-", 0x16: "*", 0x17: "/", 0x18: "%"}
INVALID = ("obj", "OBJECT_INVALID")


RENDER_LIMIT = 4000  # tree nodes; added 2026-10-23, see render()


def _tree_size(v, memo, cap):
    """Nodes of an expression tree counted as a tree (shared parts count each time), stopping
    once cap is passed. memo is by id() of the shared sub-expressions."""
    if not isinstance(v, tuple):
        return 1
    key = id(v)
    if key in memo:
        return memo[key]
    n = 1
    k = v[0]
    kids = v[2] if k == "call" else (v[2:4] if k == "op" else (v[1:2] if k in ("not", "neg", "comp") else ()))
    for a in kids:
        n += _tree_size(a, memo, cap)
        if n > cap:
            break
    memo[key] = n
    return n


def _tree_hash(v, memo):
    if not isinstance(v, tuple):
        h = 0x811C9DC5  # FNV-1a, not hash(): str hashes change from run to run
        for ch in repr(v).encode("latin-1", "replace"):
            h = ((h ^ ch) * 0x01000193) & 0xFFFFFFFF
        return h
    key = id(v)
    if key not in memo:
        k = v[0]
        kids = v[2] if k == "call" else (v[2:4] if k == "op" else (v[1:2] if k in ("not", "neg", "comp") else ()))
        h = 0x811C9DC5
        for part in [repr(v[0]), repr(v[1]) if len(v) > 1 and not isinstance(v[1], tuple) else ""] + \
                [str(_tree_hash(a, memo)) for a in kids]:
            for ch in part.encode("latin-1", "replace"):
                h = ((h ^ ch) * 0x01000193) & 0xFFFFFFFF
        memo[key] = h
    return memo[key]


def render(v):
    # A loop that keeps rebuilding a value from itself (unk_m41ac's k_punk_41ac_en, some
    # Tatooine and Kashyyyk scripts) makes a shared expression whose text grows exponentially.
    # Past RENDER_LIMIT tree nodes, name it by a structural hash instead (no Taris or Endar
    # Spire script comes near the limit, so their output is unchanged).
    if not isinstance(v, tuple):
        return _render(v)
    hit = _RCACHE.get(id(v))
    if hit is not None and hit[0] is v:
        return hit[1]
    if _tree_size(v, {}, RENDER_LIMIT) > RENDER_LIMIT:
        out = "<large expression %08x>" % _tree_hash(v, {})
    else:
        out = _render(v)
    if len(_RCACHE) > 200000:
        _RCACHE.clear()
    _RCACHE[id(v)] = (v, out)  # keeps v alive, so its id is not reused while cached
    return out


_RCACHE = {}


def _render(v):
    if isinstance(v, bool):
        return str(int(v))
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return "%g" % v
    if isinstance(v, str):
        return '"' + v + '"'
    k = v[0]
    if k == "call":
        return "%s(%s)" % (v[1], ", ".join(render(a) for a in v[2]))
    if k == "op":
        return "(%s %s %s)" % (render(v[2]), v[1], render(v[3]))
    if k == "not":
        return "!" + render(v[1])
    if k == "neg":
        return "-" + render(v[1])
    if k == "comp":
        return "~" + render(v[1])
    if k in ("obj", "unk"):
        return v[1]
    return repr(v)


def _fold(sym, a, b):
    if isinstance(a, int) and isinstance(b, int):
        try:
            r = {"&&": lambda: int(bool(a) and bool(b)), "||": lambda: int(bool(a) or bool(b)),
                 "|": lambda: a | b, "^": lambda: a ^ b, "&": lambda: a & b,
                 "==": lambda: int(a == b), "!=": lambda: int(a != b), ">=": lambda: int(a >= b),
                 ">": lambda: int(a > b), "<": lambda: int(a < b), "<=": lambda: int(a <= b),
                 "+": lambda: a + b, "-": lambda: a - b, "*": lambda: a * b,
                 "/": lambda: int(a / b), "%": lambda: a - b * int(a / b),
                 "<<": lambda: a << (b & 31), ">>": lambda: a >> (b & 31)}[sym]()
            # NWScript ints are 32 bits; a loop that doubles or shifts a value (Tatooine,
            # Kashyyyk and unk_m41ac scripts) made Python ints of gigabytes. Wrap as the engine
            # does (added 2026-10-23; values that fit 32 bits are unchanged).
            if isinstance(r, int) and not -0x80000000 <= r <= 0x7FFFFFFF:
                r = (r + 0x80000000) % 0x100000000 - 0x80000000
            return r
        except (KeyError, ZeroDivisionError, ValueError):
            return None
    if isinstance(a, str) and isinstance(b, str):
        if sym == "+":
            return a + b
        if sym == "==":
            return int(a.lower() == b.lower())
        if sym == "!=":
            return int(a.lower() != b.lower())
    if isinstance(a, tuple) and isinstance(b, tuple) and a == INVALID and b == INVALID and sym in ("==", "!="):
        return int(sym == "==")
    return None


CMP = {"==": lambda a, b: a == b, "!=": lambda a, b: a != b, ">=": lambda a, b: a >= b,
       ">": lambda a, b: a > b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b}
NEG = {"==": "!=", "!=": "==", ">=": "<", "<": ">=", ">": "<=", "<=": ">"}
FLIP = {">=": "<=", "<=": ">=", ">": "<", "<": ">", "==": "==", "!=": "!="}


def eqinfo(v):
    """(symbolic side, comparison, int) for a comparison of an expression with a constant."""
    if isinstance(v, tuple) and v[0] == "op" and v[1] in CMP:
        a, b = v[2], v[3]
        if isinstance(b, int) and isinstance(a, tuple):
            return a, v[1], b
        if isinstance(a, int) and isinstance(b, tuple):
            return b, FLIP[v[1]], a
    return None


def interval_truth(assume, rx, sym, k):
    """Decide "x sym k" from the bounds and exclusions known for x, or None."""
    lo = assume.get("lo:" + rx)
    hi = assume.get("hi:" + rx)
    excl = assume.get("ne:" + rx, ())
    if sym in ("==", "!="):
        if (lo is not None and k < lo) or (hi is not None and k > hi) or k in excl:
            eq = False
        elif lo is not None and lo == hi:
            eq = lo == k
        else:
            return None
        return eq if sym == "==" else (not eq)
    if sym == ">=":
        if lo is not None and lo >= k:
            return True
        if hi is not None and hi < k:
            return False
    elif sym == ">":
        if lo is not None and lo > k:
            return True
        if hi is not None and hi <= k:
            return False
    elif sym == "<=":
        if hi is not None and hi <= k:
            return True
        if lo is not None and lo > k:
            return False
    elif sym == "<":
        if hi is not None and hi < k:
            return True
        if lo is not None and lo >= k:
            return False
    return None


def interval_set(assume, rx, sym, k):
    lo = assume.get("lo:" + rx)
    hi = assume.get("hi:" + rx)
    if sym == "==":
        lo, hi = k, k
    elif sym == ">=":
        lo = k if lo is None else max(lo, k)
    elif sym == ">":
        lo = k + 1 if lo is None else max(lo, k + 1)
    elif sym == "<=":
        hi = k if hi is None else min(hi, k)
    elif sym == "<":
        hi = k - 1 if hi is None else min(hi, k - 1)
    elif sym == "!=":
        assume["ne:" + rx] = tuple(assume.get("ne:" + rx, ())) + (k,)
    if lo is not None:
        assume["lo:" + rx] = lo
    if hi is not None:
        assume["hi:" + rx] = hi


def truth(v, assume):
    """True / False / None (unknown) under the assumptions made on this path."""
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return None
    key = render(v)
    if key in assume:
        return assume[key]
    ei = eqinfo(v)
    if ei:
        r = interval_truth(assume, render(ei[0]), ei[1], ei[2])
        if r is not None:
            return r
    k = v[0]
    if k == "not":
        t = truth(v[1], assume)
        return None if t is None else (not t)
    if k == "op" and v[1] in ("&&", "&"):
        ta, tb = truth(v[2], assume), truth(v[3], assume)
        if ta is False or tb is False:
            return False
        if ta and tb:
            return True
        return None
    if k == "op" and v[1] in ("||", "|"):
        ta, tb = truth(v[2], assume), truth(v[3], assume)
        if ta or tb:
            return True
        if ta is False and tb is False:
            return False
        return None
    if k == "op" and v[1] in ("==", "!=") and isinstance(v[3], int) and isinstance(v[2], tuple):
        # x == 0 is the negation of x
        if v[3] == 0:
            t = truth(v[2], assume)
            if t is not None:
                return (not t) if v[1] == "==" else t
    if k == "call" and v[1] == "GetIsObjectValid" and v[2] and v[2][0] == INVALID:
        return False
    if v == INVALID:
        return False
    return None


def assume_set(assume, v, b):
    if isinstance(v, (int, float, str)):
        return
    assume[render(v)] = b
    ei = eqinfo(v)
    if ei:
        interval_set(assume, render(ei[0]), ei[1] if b else NEG[ei[1]], ei[2])
    k = v[0]
    if k == "not":
        assume_set(assume, v[1], not b)
    elif k == "op" and v[1] in ("&&", "&") and b:
        assume_set(assume, v[2], True)
        assume_set(assume, v[3], True)
    elif k == "op" and v[1] in ("||", "|") and not b:
        assume_set(assume, v[2], False)
        assume_set(assume, v[3], False)
    elif k == "op" and v[1] in ("&&", "&") and not b:
        # not (a and b): if one side is known true, the other is false
        if truth(v[2], assume) is True:
            assume_set(assume, v[3], False)
        elif truth(v[3], assume) is True:
            assume_set(assume, v[2], False)
    elif k == "op" and v[1] in ("||", "|") and b:
        if truth(v[2], assume) is False:
            assume_set(assume, v[3], True)
        elif truth(v[3], assume) is False:
            assume_set(assume, v[2], True)
    elif k == "op" and v[1] in ("==", "!=") and v[3] == 0 and isinstance(v[2], tuple):
        assume_set(assume, v[2], (not b) if v[1] == "==" else b)


def dnf(v, b, limit=64):
    """Alternatives (each a list of (value, truth)) under which v has truth b."""
    if isinstance(v, tuple) and v[0] == "not":
        return dnf(v[1], not b, limit)
    if isinstance(v, tuple) and v[0] == "op" and v[1] in ("&&", "||", "&", "|"):
        conj = (v[1] in ("&&", "&")) == b
        left, right = dnf(v[2], b, limit), dnf(v[3], b, limit)
        if conj:
            out = [x + y for x in left for y in right]
        else:
            out = left + right
        return out[:limit]
    return [[(v, b)]]


def consistent(conds):
    """False when the (value, truth) list contradicts itself."""
    assume = {}
    for v, b in conds:
        t = truth(v, assume)
        if t is not None and t != b:
            return False
        assume_set(assume, v, b)
    return True


class Path:
    __slots__ = ("pc", "st", "bp", "rets", "conds", "calls", "assume", "visits", "ret", "flags", "steps")

    def __init__(self, pc):
        self.pc = pc
        self.st = []
        self.bp = 0
        self.rets = []
        self.conds = []
        self.calls = []
        self.assume = {}
        self.visits = {}
        self.ret = None
        self.flags = set()
        self.steps = 0

    def fork(self):
        p = Path(self.pc)
        p.st = list(self.st)
        p.bp = self.bp
        p.rets = list(self.rets)
        p.conds = list(self.conds)
        p.calls = list(self.calls)
        p.assume = dict(self.assume)
        p.visits = dict(self.visits)
        p.flags = set(self.flags)
        p.steps = self.steps
        return p


# Engine routines that make a subroutine worth following path by path. A subroutine
# that reaches none of these (directly or through its own calls) is skipped: its stack
# effect is applied and its return value becomes unknown. This keeps the large include
# libraries (the generic AI in k_inc_generic and friends) from multiplying paths.
RELEVANT = {
    "SetGlobalBoolean", "SetGlobalNumber", "GetGlobalBoolean", "GetGlobalNumber",
    "AddJournalQuestEntry", "RemoveJournalQuestEntry", "GetJournalEntry",
    "GiveXPToCreature", "GivePlotXP", "CreateItemOnObject", "GiveGoldToCreature",
    "TakeGoldFromCreature", "AdjustAlignment", "DestroyObject", "SetLocked", "ActionOpenDoor",
    "ExecuteScript", "StartNewModule", "AddPartyMember", "AddAvailableNPCByTemplate",
    "ActionGiveItem", "ActionTakeItem", "GiveItem", "GetItemPossessedBy",
}


MAX_TOTAL_STEPS = 6000000  # k_ai_master, the largest common script, needs 2.34 million


class FnInfo:
    __slots__ = ("delta", "retwrites", "relevant")

    def __init__(self, delta, retwrites, relevant):
        self.delta = delta
        self.retwrites = retwrites
        self.relevant = relevant


class Machine:
    def __init__(self, code, routines, max_paths=3000, max_steps=40000, loop_limit=2, fninfo=None, budget=None,
                 params=None):
        self.code = code
        self.R = routines
        # KotOR 2 conversations run a script with five numbers and a string (a dialog node's
        # ActionParam1..5 and ActionParamStrA, or a link's Param1..5 and ParamStrA), read by
        # GetScriptParameter(1..5) and GetScriptStringParameter(). With params set they are
        # those constants, so the branches on them fold (added 2026-10-23).
        self.params = params
        self.max_paths = max_paths
        self.max_steps = max_steps
        self.loop_limit = loop_limit
        self.truncated = False
        self.fninfo = fninfo if fninfo is not None else {}
        self._busy = set()
        # Steps over all paths and subroutine runs of one script. A script whose subroutines
        # each fork many paths (unk_m41ac's k_punk_41ac_en, some Tatooine and Kashyyyk area
        # scripts) otherwise runs for hours. Past the budget every path ends, flagged
        # truncated (added 2026-10-23; the Taris and Endar Spire scripts stay far below it).
        self.budget = budget if budget is not None else [0]  # shared with deferred-action machines
        self.max_total_steps = MAX_TOTAL_STEPS

    # ------------------------------------------------------------ static walk
    def _stack_effect(self, pc):
        """(cells popped, cells pushed, next pc list, size) for the static walk; None = unknown."""
        c = self.code
        op, t = c[pc], c[pc + 1]
        if op == 0x01:
            return 0, 0, [pc + 8]
        if op == 0x02:
            return 0, 1, [pc + 2]
        if op == 0x03:
            return 0, self.i16(pc + 6) // 4, [pc + 8]
        if op == 0x04:
            if t == 5:
                return 0, 1, [pc + 4 + self.u16(pc + 2)]
            return 0, 1, [pc + 6]
        if op == 0x05:
            rid = self.u16(pc + 2)
            argc = c[pc + 4]
            _name, rett, params = self.R[rid] if rid < len(self.R) else ("?", "void", [])
            pops = 0
            for ptype, _n in params[:argc]:
                if ptype == "action":
                    continue
                pops += 3 if ptype == "vector" else 1
            push = 3 if rett == "vector" else (0 if rett == "void" else 1)
            return pops, push, [pc + 5]
        if 0x06 <= op <= 0x18:
            if op in (0x0B, 0x0C) and t == 0x24:
                return 2 * (self.u16(pc + 2) // 4), 1, [pc + 4]
            if t == 0x3A:
                return 6, 3, [pc + 2]
            if t in (0x3B, 0x3C):
                return 4, 3, [pc + 2]
            return 2, 1, [pc + 2]
        if op in (0x19, 0x1A, 0x22, 0x2D):
            return 0, 0, [pc + 2]
        if op == 0x1B:
            return -self.i32(pc + 2) // 4, 0, [pc + 6]
        if op == 0x1D:
            return 0, 0, [pc + self.i32(pc + 2)]
        if op in (0x1F, 0x25):
            return 1, 0, [pc + 6, pc + self.i32(pc + 2)]
        if op == 0x21:
            return self.i16(pc + 2) // 4, self.i16(pc + 6) // 4, [pc + 8]
        if op in (0x23, 0x24, 0x28, 0x29):
            return 0, 0, [pc + 6]
        if op == 0x26:
            return 0, 0, [pc + 8]
        if op == 0x27:
            return 0, self.i16(pc + 6) // 4, [pc + 8]
        if op == 0x2A:
            return 0, 1, [pc + 2]
        if op == 0x2B:
            return 1, 0, [pc + 2]
        if op == 0x2C:
            return 0, 0, [pc + 10]
        return None

    def info(self, entry):
        """Summary of the subroutine at entry (FnInfo), or None when it cannot be walked."""
        if entry in self.fninfo:
            return self.fninfo[entry]
        if entry in self._busy:
            return None
        self._busy.add(entry)
        c = self.code
        seen = {}
        work = [(entry, 0)]
        delta = None
        retwrites = set()
        relevant = False
        ok = True
        blocks = []
        while work and ok:
            pc, d = work.pop()
            while True:
                if pc in seen or pc + 1 >= len(c):
                    break
                seen[pc] = d
                op = c[pc]
                if op == 0x20:
                    if delta is None:
                        delta = d
                    break
                if op == 0x1E:
                    sub = self.info(pc + self.i32(pc + 2))
                    if sub is None:
                        ok = False
                        break
                    relevant = relevant or sub.relevant
                    d += sub.delta
                    pc += 6
                    continue
                if op == 0x05:
                    rid = self.u16(pc + 2)
                    if rid < len(self.R) and self.R[rid][0] in RELEVANT:
                        relevant = True
                if op == 0x01:
                    off = self.i32(pc + 2) // 4
                    if d + off < 0:
                        retwrites.add(d + off)
                if op == 0x2C and c[pc + 10] == 0x1D:
                    blocks.append(pc + 16)
                eff = self._stack_effect(pc)
                if eff is None:
                    ok = False
                    break
                pops, push, nxts = eff
                d = d - pops + push
                if len(nxts) == 2:
                    work.append((nxts[1], d))
                pc = nxts[0]
        # deferred action blocks: only their relevance matters
        for b in blocks:
            if relevant or not ok:
                break
            bi = self.info(b)
            if bi is None or bi.relevant:
                relevant = True
        self._busy.discard(entry)
        if not ok or delta is None:
            self.fninfo[entry] = None
            return None
        fi = FnInfo(delta, sorted(retwrites), relevant)
        self.fninfo[entry] = fi
        return fi

    def i16(self, p):
        return struct.unpack_from(">h", self.code, p)[0]

    def u16(self, p):
        return struct.unpack_from(">H", self.code, p)[0]

    def i32(self, p):
        return struct.unpack_from(">i", self.code, p)[0]

    def run(self, entry=13, start=None, depth=0):
        """Run all paths from entry; returns the list of finished Path objects."""
        first = start if start is not None else Path(entry)
        first.pc = entry
        work = [first]
        done = []
        made = 1
        while work:
            p = work.pop()
            while True:
                r = self.step(p, depth)
                if r is None:
                    continue
                if r == "end":
                    done.append(p)
                    break
                if isinstance(r, Path):
                    made += 1
                    if made > self.max_paths:
                        self.truncated = True
                        p.flags.add("truncated")
                    else:
                        work.append(r)
                    continue
        return done

    def step(self, p, depth):
        """Execute one instruction. None = continue, "end" = path finished, Path = a fork."""
        c = self.code
        pc = p.pc
        p.steps += 1
        self.budget[0] += 1
        if self.budget[0] > self.max_total_steps:
            self.truncated = True
            p.flags.add("truncated")
            return "end"
        if p.steps > self.max_steps or pc + 1 >= len(c):
            p.flags.add("step-limit" if p.steps > self.max_steps else "ran-off-end")
            return "end"
        op, t = c[pc], c[pc + 1]
        st = p.st
        try:
            if op == 0x01:  # CPDOWNSP
                off = self.i32(pc + 2) // 4
                n = self.i16(pc + 6) // 4
                src = st[-n:]
                for k in range(n):
                    idx = len(st) + off + k
                    if 0 <= idx < len(st):
                        st[idx] = src[k]
                p.pc = pc + 8
            elif op == 0x02:  # RSADD
                st.append({3: 0, 4: 0.0, 5: "", 6: INVALID}.get(t, ("unk", "var")))
                p.pc = pc + 2
            elif op == 0x03:  # CPTOPSP
                off = self.i32(pc + 2) // 4
                n = self.i16(pc + 6) // 4
                idx = len(st) + off
                for k in range(n):
                    st.append(st[idx + k] if 0 <= idx + k < len(st) else ("unk", "?"))
                p.pc = pc + 8
            elif op == 0x04:  # CONST
                if t == 3:
                    st.append(self.i32(pc + 2))
                    p.pc = pc + 6
                elif t == 4:
                    st.append(struct.unpack_from(">f", c, pc + 2)[0])
                    p.pc = pc + 6
                elif t == 5:
                    n = self.u16(pc + 2)
                    st.append(c[pc + 4:pc + 4 + n].decode("latin-1"))
                    p.pc = pc + 4 + n
                elif t == 6:
                    o = self.i32(pc + 2)
                    st.append(("obj", "OBJECT_SELF" if o == 0 else "OBJECT_INVALID" if o == 1 else "obj%d" % o))
                    p.pc = pc + 6
                else:
                    raise ValueError("const type %d" % t)
            elif op == 0x05:  # ACTION
                rid = self.u16(pc + 2)
                argc = c[pc + 4]
                name, rett, params = self.R[rid] if rid < len(self.R) else ("routine%d" % rid, "void", [])
                args = []
                for ptype, _pname in params[:argc]:
                    if ptype == "action":
                        args.append(("unk", "<action>"))
                    elif ptype == "vector":
                        for _ in range(3):
                            if st:
                                st.pop()
                        args.append(("unk", "vector"))
                    else:
                        args.append(st.pop() if st else ("unk", "?"))
                p.calls.append((name, tuple(args), False))
                if rett == "vector":
                    st.extend([("unk", "vector")] * 3)
                elif self.params is not None and name == "GetScriptParameter" and args \
                        and isinstance(args[0], int) and 1 <= args[0] <= 5:
                    st.append(self.params[args[0] - 1])
                elif self.params is not None and name == "GetScriptStringParameter":
                    st.append(self.params[5])
                elif rett != "void":
                    st.append(("call", name, tuple(args)))
                p.pc = pc + 5
            elif 0x06 <= op <= 0x18:
                if op in (0x0B, 0x0C) and t == 0x24:
                    n = self.u16(pc + 2) // 4
                    del st[len(st) - 2 * n:]
                    st.append(("unk", "struct-compare"))
                    p.pc = pc + 4
                else:
                    if t == 0x3A:
                        pops, push = 6, 3
                    elif t in (0x3B, 0x3C):
                        pops, push = 4, 3
                    else:
                        pops, push = 2, 1
                    if pops == 2 and len(st) >= 2:
                        b = st.pop()
                        a = st.pop()
                        sym = OPS.get(op, "op")
                        f = _fold(sym, a, b)
                        st.append(f if f is not None else ("op", sym, a, b))
                    else:
                        del st[max(0, len(st) - pops):]
                        st.extend([("unk", "vector")] * push)
                    p.pc = pc + 2
            elif op in (0x19, 0x1A, 0x22):  # NEG COMP NOT
                if st:
                    a = st.pop()
                    if op == 0x19:
                        st.append(-a if isinstance(a, (int, float)) else ("neg", a))
                    elif op == 0x22:
                        st.append(int(not a) if isinstance(a, int) else ("not", a))
                    else:
                        st.append(~a if isinstance(a, int) else ("comp", a))
                p.pc = pc + 2
            elif op == 0x1B:  # MOVSP
                n = -self.i32(pc + 2) // 4
                del st[max(0, len(st) - n):]
                p.pc = pc + 6
            elif op == 0x1D:  # JMP
                p.pc = pc + self.i32(pc + 2)
            elif op == 0x1E:  # JSR
                fi = self.info(pc + self.i32(pc + 2))
                if fi is not None and not fi.relevant:
                    # skip an irrelevant subroutine: apply its stack effect, forget its result
                    base = len(st)
                    if fi.delta < 0:
                        del st[len(st) + fi.delta:]
                    else:
                        st.extend([("unk", "sub")] * fi.delta)
                    for r in fi.retwrites:
                        idx = base + r
                        if 0 <= idx < len(st):
                            st[idx] = ("unk", "sub-result")
                    p.pc = pc + 6
                    return None
                p.rets.append(pc + 6)
                if len(p.rets) > 200:
                    raise ValueError("call depth")
                p.pc = pc + self.i32(pc + 2)
            elif op in (0x1F, 0x25):  # JZ JNZ
                v = st.pop() if st else ("unk", "?")
                tgt = pc + self.i32(pc + 2)
                nxt = pc + 6
                tv = truth(v, p.assume)
                # JZ jumps when v is false; JNZ jumps when v is true
                jump_when = False if op == 0x1F else True
                if tv is not None:
                    p.pc = tgt if tv == jump_when else nxt
                    return None
                cnt = p.visits.get(pc, 0) + 1
                p.visits[pc] = cnt
                if cnt > self.loop_limit:
                    # loop guard: take the exit (JZ jumps out of a while loop)
                    p.flags.add("loop-cut")
                    p.pc = tgt if op == 0x1F else nxt
                    return None
                q = p.fork()
                # p: jump branch, q: fall-through branch
                p.conds.append((v, jump_when))
                assume_set(p.assume, v, jump_when)
                p.pc = tgt
                q.conds.append((v, not jump_when))
                assume_set(q.assume, v, not jump_when)
                q.pc = nxt
                return q
            elif op == 0x20:  # RETN
                if p.rets:
                    p.pc = p.rets.pop()
                else:
                    p.ret = st[0] if st else None
                    return "end"
            elif op == 0x21:  # DESTRUCT
                size = self.i16(pc + 2) // 4
                keepoff = self.i16(pc + 4) // 4
                keep = self.i16(pc + 6) // 4
                blk = st[len(st) - size:]
                kept = blk[keepoff:keepoff + keep]
                del st[len(st) - size:]
                st.extend(kept)
                p.pc = pc + 8
            elif op in (0x23, 0x24, 0x28, 0x29):  # DECISP INCISP DECIBP INCIBP
                off = self.i32(pc + 2) // 4
                idx = (len(st) if op in (0x23, 0x24) else p.bp) + off
                if 0 <= idx < len(st):
                    v = st[idx]
                    d = -1 if op in (0x23, 0x28) else 1
                    st[idx] = v + d if isinstance(v, int) else ("op", "+", v, d)
                p.pc = pc + 6
            elif op == 0x26:  # CPDOWNBP
                off = self.i32(pc + 2) // 4
                n = self.i16(pc + 6) // 4
                src = st[-n:]
                for k in range(n):
                    idx = p.bp + off + k
                    if 0 <= idx < len(st):
                        st[idx] = src[k]
                p.pc = pc + 8
            elif op == 0x27:  # CPTOPBP
                off = self.i32(pc + 2) // 4
                n = self.i16(pc + 6) // 4
                idx = p.bp + off
                for k in range(n):
                    st.append(st[idx + k] if 0 <= idx + k < len(st) else ("unk", "global"))
                p.pc = pc + 8
            elif op == 0x2A:  # SAVEBP: BP takes the current SP, then the old BP is pushed
                # (CPTOPBP -4 then reads the last global, which is what the compiler emits)
                old = p.bp
                p.bp = len(st)
                st.append(("unk", "bp:%d" % old))
                p.pc = pc + 2
            elif op == 0x2B:  # RESTOREBP
                v = st.pop() if st else None
                if isinstance(v, tuple) and v[0] == "unk" and v[1].startswith("bp:"):
                    p.bp = int(v[1][3:])
                p.pc = pc + 2
            elif op == 0x2C:  # STORE_STATE, then a JMP over the deferred action block
                blk = pc + 10
                if c[blk] == 0x1D and depth < 6:
                    sub = Path(blk + 6)
                    sub.st = list(st)
                    sub.bp = p.bp
                    sub.assume = dict(p.assume)
                    m = Machine(c, self.R, max_paths=50, max_steps=5000, loop_limit=self.loop_limit,
                                fninfo=self.fninfo, budget=self.budget, params=self.params)
                    seen = set()
                    for sp in m.run(blk + 6, sub, depth + 1):
                        for call in sp.calls:
                            key = (call[0], call[1])
                            if key not in seen:
                                seen.add(key)
                                p.calls.append((call[0], call[1], True))
                    if m.truncated:
                        p.flags.add("truncated")
                p.pc = pc + 10
            elif op == 0x2D:  # NOP
                p.pc = pc + 2
            elif op == 0x42:  # file header byte, if ever reached
                p.pc = pc + 5
            else:
                raise ValueError("opcode %02x at %d" % (op, pc))
        except (struct.error, IndexError, ValueError) as e:
            p.flags.add("error:" + str(e))
            return "end"
        return None


def run_script(data, routines, params=None):
    """All finished paths of an NCS file, plus a truncated flag. params: (p1, p2, p3, p4, p5,
    string) for a KotOR 2 script run with parameters, else None."""
    if data[:8] != b"NCS V1.0":
        return [], False
    key = _cache_key(data, routines, params)
    hit = _cache_get(key)
    if hit is not None:
        return hit
    m = Machine(data, routines, params=params)
    paths = m.run(13)
    out = (paths, m.truncated or any("truncated" in p.flags for p in paths))
    _cache_put(key, out)
    return out


# A disk cache of run_script's results, shared by every process and run (added 2026-10-23: the
# same generic AI and spawn scripts are analysed in every module of every chapter, which made a
# KotOR 2 chapter build take an hour). The key holds everything the result depends on: the
# script's bytes, its parameters, the engine routine table, RELEVANT, the step limits and this
# file's own code, so a change to the interpreter starts a fresh cache. KMRP_NCS_CACHE=0 turns
# it off; the folder is save-editor/build/questdb-cache (ignored by git).
import hashlib  # noqa: E402
import os  # noqa: E402
import pickle  # noqa: E402

_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "build", "questdb-cache")
_CACHE_ON = os.environ.get("KMRP_NCS_CACHE", "1") != "0"
with open(os.path.abspath(__file__), "rb") as _f:
    _CODE = hashlib.sha1(_f.read()).hexdigest()
_ROUTINES = {}


def _cache_key(data, routines, params):
    rid = id(routines)
    if rid not in _ROUTINES:
        _ROUTINES[rid] = (routines, hashlib.sha1(repr(routines).encode("latin-1", "replace")).hexdigest())
    h = hashlib.sha1()
    for part in (_CODE, _ROUTINES[rid][1], repr(params), repr(sorted(RELEVANT)), repr(MAX_TOTAL_STEPS)):
        h.update(part.encode("latin-1", "replace"))
        h.update(b"\0")
    h.update(data)
    return h.hexdigest()


def _cache_get(key):
    if not _CACHE_ON:
        return None
    try:
        with open(os.path.join(_CACHE_DIR, key[:2], key), "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def _cache_put(key, value):
    if not _CACHE_ON:
        return
    try:
        d = os.path.join(_CACHE_DIR, key[:2])
        os.makedirs(d, exist_ok=True)
        tmp = os.path.join(d, "%s.%d.tmp" % (key, os.getpid()))
        with open(tmp, "wb") as f:
            pickle.dump(value, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, os.path.join(d, key))
    except Exception:
        pass
