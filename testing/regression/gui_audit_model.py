"""Read-only GUI audit model. Engine facts and explicit assumptions are in the report."""
from __future__ import annotations
import math
import copy
import re
import struct
from dataclasses import dataclass, field
from functools import lru_cache
from pykotor.resource.formats.gff import read_gff

FIELDS = ('LEFT', 'TOP', 'WIDTH', 'HEIGHT')

@dataclass
class Node:
    path: str
    tag: str
    rect: tuple
    kind: int
    font: str = ''
    text: str = ''
    strref: int = -1
    border: int = 0
    padding: int = 0
    leftbar: bool = False
    art: str = ''
    fillstyle: int = 0
    children: list = field(default_factory=list)
    proto: object = None
    bar: object = None


def nodes(data):
    def walk(s, path):
        e = s.acquire('EXTENT', None)
        t, b = s.acquire('TEXT', None), s.acquire('BORDER', None)
        tag = s.acquire('TAG', '') or path.rsplit('/', 1)[-1]
        n = Node(path, tag, tuple(e.acquire(k, 0) for k in FIELDS) if e else (0, 0, 0, 0),
                 s.acquire('CONTROLTYPE', -1))
        if t:
            n.font = str(t.acquire('FONT', '')).lower()
            n.text, n.strref = t.acquire('TEXT', ''), t.acquire('STRREF', -1)
        if b:
            n.border, n.art = b.acquire('DIMENSION', 0), str(b.acquire('FILL', '')).lower()
            n.fillstyle = b.acquire('FILLSTYLE', 0)
        n.padding, n.leftbar = s.acquire('PADDING', 0), bool(s.acquire('LEFTSCROLLBAR', 0))
        for i, c in enumerate(s.acquire('CONTROLS', []) or []):
            n.children.append(walk(c, path + '/' + (c.acquire('TAG', '') or str(i))))
        for key, attr in [('PROTOITEM', 'proto'), ('SCROLLBAR', 'bar')]:
            sub = s.acquire(key, None)
            if sub: setattr(n, attr, walk(sub, path + '/' + key))
        return n
    return walk(read_gff(data).root, 'root')


def flatten(n):
    yield n
    for c in n.children: yield from flatten(c)
    for c in (n.proto, n.bar):
        if c: yield from flatten(c)


def field_locations(data):
    """Map inline GFF data FILE offsets to recursive control paths and field names."""
    from build_gui_blend_table import Gff
    g = Gff(data)
    result = {}
    def walk(index, path):
        fields = g.fields(index)
        for label, entry in fields.items():
            if label == 'EXTENT':
                for name, field in g.fields(g.dword(entry)).items():
                    result[field+8] = (path, name)
            elif label == 'CONTROLS':
                for i in g.list(entry):
                    sub = g.fields(i)
                    walk(i,path+'/'+(g.string(sub['TAG']) if 'TAG' in sub else str(i)))
            elif label in ('PROTOITEM','SCROLLBAR'):
                walk(g.dword(entry),path+'/'+label)
            elif struct.unpack_from('<I',data,entry)[0] in (0,1,2,3,4,5,8):
                result[entry+8] = (path,label)
    walk(0,'root')
    return result


def blended_reference(roots, weights):
    """Unmodified upstream extents blended once, as derive_resolution_gui_set.blend.

    Non-extent audit fields and hierarchy must match; otherwise inheritance is
    unresolved. No generated resource or source node is changed.
    """
    maps = [{n.path:n for n in flatten(root)} for root in roots]
    if not maps or any(set(m)!=set(maps[0]) for m in maps): return None
    static=('tag','kind','font','text','strref','border','padding','leftbar','art','fillstyle')
    for path,first in maps[0].items():
        if any(any(getattr(first,k)!=getattr(m[path],k) for k in static) for m in maps[1:]): return None
    def clone(n):
        made=copy.copy(n)
        made.rect=tuple(int(math.copysign(math.floor(abs(v)+.5),v))
                        for v in (sum(m[n.path].rect[i]*w for m,w in zip(maps,weights)) for i in range(4)))
        made.children=[clone(c) for c in n.children]
        made.proto=clone(n.proto) if n.proto else None
        made.bar=clone(n.bar) if n.bar else None
        return made
    return clone(roots[0])


class Font:
    def __init__(self, data):
        lines = data.decode('ascii', errors='replace').splitlines()
        scalars, coords = {}, {}
        i = 0
        while i < len(lines):
            p = lines[i].split(); i += 1
            if not p: continue
            if p[0].lower() in ('upperleftcoords', 'lowerrightcoords'):
                count = int(p[1]); coords[p[0].lower()] = [float(lines[i+j].split()[0]) for j in range(count)]
                i += count
            elif len(p) > 1:
                try: scalars[p[0].lower()] = float(p[1])
                except ValueError: pass
        self.height = scalars['fontheight'] * 100
        self.spacing = scalars.get('spacingr', 0) * 100
        self.widths = [(b-a) * scalars['texturewidth'] * 100 for a, b in
                       zip(coords['upperleftcoords'], coords['lowerrightcoords'])]

    @lru_cache(maxsize=20000)
    def width(self, text):
        raw = text.encode('cp1252', errors='replace')
        return sum(self.widths[c] for c in raw) + max(0, len(raw)-1) * self.spacing

    def wrap(self, text, width):
        """Space wrapping; unbreakable words are retained and checked separately."""
        out = []
        for paragraph in text.replace('\r', '').split('\n'):
            line = ''
            for word in paragraph.split():
                candidate = line + (' ' if line else '') + word
                if line and self.width(candidate) > width:
                    out.append(line); line = word
                else: line = candidate
            out.append(line)
        return out


def overshoot(rect, bounds):
    x, y, w, h = rect; bx, by, bw, bh = bounds
    return max(0, bx-x, by-y, x+w-bx-bw, y+h-by-bh)


def overlap(a, b):
    x = min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0])
    y = min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1])
    return min(x, y) if x > 0 and y > 0 else 0


def row_height(base, height):
    f32 = lambda x: struct.unpack('<f', struct.pack('<f', x))[0]
    return round(f32(f32(base) * max(1, f32(height / 720))))


def status_summary(width, height, font, widest, count):
    line = int(font.height + .5)
    at = lambda v: (v * line + 8) // 16
    lx = at(52); lw = math.floor(widest+.5) + line//4
    bw = lx + lw + at(10)
    if bw > width: bw = width; lw = bw-lx-at(10)
    ow, oh = at(100), at(22)
    bw = max(bw, min(width, ow+2*(oh+oh//4+at(4))))
    rows = [(lx, at(10)+n*at(37)-at(1), lw, at(32)) for n in range(count)]
    oy = at(10)+count*at(37)-at(7); bh = oy+at(32)
    return ((width-bw)//2, (height-bh)//2, bw, bh), rows, ((bw-ow)//2, oy, ow, oh)


def popup_fit(root, font, text, shown_ok, shown_cancel, shown_icon):
    """Reimplementation of popup_fit.cpp, with modelled engine wrapping/client height."""
    controls = {c.tag: c for c in root.children}
    msg, ok, cancel = (controls[k] for k in ('LB_MESSAGE','BTN_OK','BTN_CANCEL'))
    icon = next((c for c in root.children if 'ICON' in c.tag), None)
    m, o, c, p = map(list, (msg.rect, ok.rect, cancel.rect, root.rect))
    bar = msg.bar.rect[2] if msg.bar else 0
    content = lambda w: max(1, w-bar-2*msg.border-msg.padding)
    item = len(font.wrap(text, content(m[2]))) * font.height
    # The native hook deliberately leaves messages requiring scrollbars alone.
    if item+msg.padding > m[3]-2*msg.border: return None
    low = max(1, o[2] if shown_ok else 0, c[2] if shown_cancel else 0,
              icon.rect[2] if shown_icon and icon else 0)
    high = m[2]
    while low < high:
        mid = low+(high-low)//2
        if len(font.wrap(text, content(mid)))*font.height == item: high = mid
        else: low = mid+1
    m[2] = high
    m[3] = math.ceil(item+msg.padding+2*msg.border)
    width = min(p[2], m[2]+2*m[0])
    o[0], o[1] = width//2-o[2]//2, m[1]+m[3]+4
    c[0], c[1] = width//2-c[2]//2, o[1]+o[3]+2
    bottom = c[1]+c[3] if shown_cancel else o[1]+o[3] if shown_ok else m[1]+m[3]
    ph = min(p[3], bottom+msg.rect[1])
    p[0] += (p[2]-width)//2; p[1] += (p[3]-ph)//2; p[2:] = width, ph
    return tuple(p), [(msg.tag, tuple(m)), *([(ok.tag,tuple(o))] if shown_ok else []),
                      *([(cancel.tag,tuple(c))] if shown_cancel else [])]


def granted_fit(root, height, count):
    controls = {c.tag:c for c in root.children}
    lst, ok = controls['LB_SKILLS'], controls['BTN_OK']
    row = row_height(50,height); inner = lst.rect[3]-2*lst.border
    rows = min(count,inner//row); cut = max(0,inner-rows*(row+row//11)) if rows else 0
    if (inner-cut)//row != rows: cut = 0
    p, l, o = map(list,(root.rect,lst.rect,ok.rect))
    p[1] += cut//2; p[3] -= cut; l[3] -= cut; o[1] -= cut
    # GrantedRowText: enlarge the hex/icon by 1/7, move down size/40,
    # inset text by size/8 at each side.
    grown = row+row//7
    return tuple(p), [(lst.tag,tuple(l)),(ok.tag,tuple(o))], (row,grown,row//8)


def scaling_rule(points, axis):
    """Least residual model across dimensions, using equal-width/height pairs only."""
    values = []
    for i, (w,h,rect) in enumerate(points):
        for ww,hh,rr in points[i+1:]:
            if (w == ww and h != hh) or (h == hh and w != ww):
                if rect[axis] > 0 and rr[axis] > 0:
                    values.append((w,h,rect[axis],ww,hh,rr[axis]))
    if not values: return 'undetermined', 0
    models = {'fixed':lambda w,h:1, 'height':lambda w,h:max(1,h/720),
              'width':lambda w,h:w, 'both':lambda w,h:w if axis==2 else h}
    residual = {name:max(abs(b/a-f(ww,hh)/f(w,h)) for w,h,a,ww,hh,b in values)
                for name,f in models.items()}
    best = min(residual,key=residual.get)
    return best if residual[best] <= .06 else 'mixed', residual[best]
