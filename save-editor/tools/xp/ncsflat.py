"""Flat NCS call scanner: every engine call site once, arguments rendered symbolically.

Origin: the emulator part of the research scratchpad's ncsscan.py (2026-10-22), copied
unchanged on 2026-10-23 (lines 17 to 214 of that file). Each function body is walked once,
so a helper called with different arguments reports only the first call's arguments;
extract_enemies.py uses the path-by-path ncsvm for those cases.
"""
import json
import struct

class Sym:
    __slots__ = ("s",)
    def __init__(self, s): self.s = s
    def __repr__(self): return self.s

def render(v):
    if isinstance(v, Sym): return v.s
    if isinstance(v, str): return json.dumps(v)
    if isinstance(v, float): return "%g" % v
    return str(v)

UNK = Sym("?")

class Fn:
    def __init__(self, code, routines):
        self.code = code
        self.R = routines
        self.calls = {}        # pc -> (name, [args])
        self.delta = {}        # function entry -> net cell delta at RETN
        self.busy = set()
        self.walked = set()
        self.errors = []

    def u8(self, p): return self.code[p]
    def i16(self, p): return struct.unpack_from(">h", self.code, p)[0]
    def u16(self, p): return struct.unpack_from(">H", self.code, p)[0]
    def i32(self, p): return struct.unpack_from(">i", self.code, p)[0]

    def run(self, entry, stack, depth=0):
        """Abstract-interpret a function from entry with given stack; return net delta at RETN."""
        if depth > 400:
            return None
        base = len(stack)
        work = [(entry, list(stack))]
        seen = {}
        ret = None
        while work:
            pc, st = work.pop()
            while True:
                if pc in seen:
                    break
                seen[pc] = len(st)
                if pc >= len(self.code):
                    break
                op = self.code[pc]; t = self.code[pc + 1]
                nxt = None
                try:
                    if op == 0x01:  # CPDOWNSP
                        off = self.i32(pc + 2) // 4; n = self.i16(pc + 6) // 4
                        src = st[-n:]
                        for k in range(n):
                            idx = len(st) + off + k
                            if 0 <= idx < len(st): st[idx] = src[k]
                        nxt = pc + 8
                    elif op == 0x02:
                        st.append(Sym("var")); nxt = pc + 2
                    elif op == 0x03:  # CPTOPSP
                        off = self.i32(pc + 2) // 4; n = self.i16(pc + 6) // 4
                        idx = len(st) + off
                        for k in range(n):
                            st.append(st[idx + k] if 0 <= idx + k < len(st) else UNK)
                        nxt = pc + 8
                    elif op == 0x04:
                        if t == 3: st.append(self.i32(pc + 2)); nxt = pc + 6
                        elif t == 4: st.append(struct.unpack_from(">f", self.code, pc + 2)[0]); nxt = pc + 6
                        elif t == 5:
                            n = self.u16(pc + 2)
                            st.append(self.code[pc + 4:pc + 4 + n].decode("latin-1")); nxt = pc + 4 + n
                        elif t == 6:
                            o = self.i32(pc + 2)
                            st.append(Sym("OBJECT_SELF" if o == 0 else "OBJECT_INVALID" if o == 1 else "obj%d" % o)); nxt = pc + 6
                        else:
                            raise ValueError("const type %d" % t)
                    elif op == 0x05:  # ACTION
                        rid = self.u16(pc + 2); argc = self.code[pc + 4]
                        name, rett, params = self.R[rid] if rid < len(self.R) else ("routine%d" % rid, "void", [])
                        args = []
                        for (ptype, pname) in params[:argc]:
                            if ptype == "action":
                                args.append(Sym("<action>")); continue
                            if ptype == "vector":
                                for _ in range(3):
                                    if st: st.pop()
                                args.append(Sym("vector"))
                            else:
                                args.append(st.pop() if st else UNK)
                        if pc not in self.calls:
                            self.calls[pc] = (name, [render(a) for a in args])
                        if rett == "vector":
                            st.extend([UNK] * 3)
                        elif rett != "void":
                            a = ", ".join(render(x) for x in args)
                            if len(a) > 80: a = a[:77] + "..."
                            st.append(Sym("%s(%s)" % (name, a)))
                        nxt = pc + 5
                    elif 0x06 <= op <= 0x18:
                        if op in (0x0B, 0x0C) and t == 0x24:
                            n = self.u16(pc + 2) // 4
                            del st[len(st) - 2 * n:]; st.append(UNK); nxt = pc + 4
                        else:
                            if t == 0x3A: pops, push = 6, 3
                            elif t in (0x3B, 0x3C): pops, push = 4, 3
                            else: pops, push = 2, 1
                            if pops == 2 and len(st) >= 2:
                                b = st.pop(); a = st.pop()
                                opn = {0x06: "&&", 0x07: "||", 0x08: "|", 0x09: "^", 0x0A: "&", 0x0B: "==", 0x0C: "!=",
                                       0x0D: ">=", 0x0E: ">", 0x0F: "<", 0x10: "<=", 0x14: "+", 0x15: "-", 0x16: "*",
                                       0x17: "/", 0x18: "%"}.get(op, "op")
                                if op == 0x14 and isinstance(a, int) and isinstance(b, int): st.append(a + b)
                                elif op == 0x14 and isinstance(a, str) and isinstance(b, str): st.append(a + b)
                                else:
                                    s = "(%s %s %s)" % (render(a), opn, render(b))
                                    st.append(Sym(s if len(s) < 100 else "(expr)"))
                            else:
                                del st[max(0, len(st) - pops):]; st.extend([UNK] * push)
                            nxt = pc + 2
                    elif op in (0x19, 0x1A, 0x22):
                        if st:
                            a = st.pop()
                            if op == 0x19 and isinstance(a, (int, float)): st.append(-a)
                            else: st.append(Sym("!" + render(a) if op == 0x22 else "~" + render(a)))
                        nxt = pc + 2
                    elif op == 0x1B:  # MOVSP
                        n = -self.i32(pc + 2) // 4
                        del st[max(0, len(st) - n):]; nxt = pc + 6
                    elif op == 0x1D:  # JMP
                        pc = pc + self.i32(pc + 2); continue
                    elif op == 0x1E:  # JSR
                        tgt = pc + self.i32(pc + 2)
                        d = self.func_delta(tgt, st, depth)
                        if d is None:
                            self.errors.append("jsr delta unknown at %d" % pc); break
                        if d < 0: del st[len(st) + d:]
                        else: st.extend([UNK] * d)
                        nxt = pc + 6
                    elif op in (0x1F, 0x25):  # JZ JNZ
                        if st: st.pop()
                        work.append((pc + self.i32(pc + 2), list(st)))
                        nxt = pc + 6
                    elif op == 0x20:  # RETN
                        ret = len(st) - base; break
                    elif op == 0x21:  # DESTRUCT
                        size = self.i16(pc + 2) // 4; keepoff = self.i16(pc + 4) // 4; keep = self.i16(pc + 6) // 4
                        blk = st[len(st) - size:]; kept = blk[keepoff:keepoff + keep]
                        del st[len(st) - size:]; st.extend(kept); nxt = pc + 8
                    elif op in (0x23, 0x24, 0x28, 0x29):
                        nxt = pc + 6
                    elif op in (0x26,):
                        nxt = pc + 8
                    elif op == 0x27:  # CPTOPBP
                        n = self.i16(pc + 6) // 4
                        st.extend([Sym("global")] * n); nxt = pc + 8
                    elif op == 0x2A:
                        st.append(UNK); nxt = pc + 2
                    elif op == 0x2B:
                        if st: st.pop()
                        nxt = pc + 2
                    elif op == 0x2C:  # STORE_STATE: next is JMP over the action block
                        blk = pc + 10
                        if self.code[blk] == 0x1D:
                            self.func_delta(blk + 6, st, depth, cache=False)
                        nxt = pc + 10
                    elif op == 0x2D:
                        nxt = pc + 2
                    elif op == 0x42:
                        nxt = pc + 5
                    else:
                        raise ValueError("opcode %02x at %d" % (op, pc))
                except (struct.error, IndexError, ValueError) as e:
                    self.errors.append(str(e)); break
                pc = nxt
        return ret

    def func_delta(self, entry, st, depth, cache=True):
        if entry in self.busy:
            return self.delta.get(entry)
        if cache and entry in self.walked:
            return self.delta.get(entry)
        if cache: self.walked.add(entry)
        self.busy.add(entry)
        d = self.run(entry, list(st), depth + 1)
        self.busy.discard(entry)
        if cache and d is not None:
            self.delta[entry] = d
        return d

def analyse(data, routines):
    if data[:8] != b"NCS V1.0":
        return None
    f = Fn(data, routines)
    f.walked = set()
    f.run(13, [], 0)
    for _ in range(3):
        if not f.errors: break
        f.calls = {}; f.errors = []; f.walked = set()
        f.run(13, [], 0)
    calls = [f.calls[k] for k in sorted(f.calls)]
    return {"calls": calls, "errors": f.errors[:5]}
