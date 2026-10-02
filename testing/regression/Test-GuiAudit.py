#!/usr/bin/env python3
"""Audit every shipped GUI and native blend. argv[1] is the resources directory."""
from __future__ import annotations
import argparse
import contextlib
import fnmatch
import hashlib
import importlib.util
import json
import logging
import math
import os
import platform
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from gui_audit_model import (Font, nodes, flatten, overshoot, overlap, row_height,
                             status_summary, popup_fit, granted_fit, scaling_rule, field_locations,
                             blended_reference)
from pykotor.resource.formats.gff import read_gff
from pykotor.resource.formats.tlk import read_tlk
from pykotor.resource.formats.twoda import read_2da
from pykotor.resource.type import ResourceType
from scale_listbox_padding import ROW_LISTS

UPSTREAM = ROOT / 'third_party/Included/kotor-high-resolution-menus-1.5'
ALLOWLIST = Path(__file__).with_name('GuiAudit-allowlist.json')
ASPECTS = (4/3, 3/2, 16/10, 16/9, 21/9, 32/9)
FALLBACK = {
 'item': ['Adrenal Strength', 'Energy Shield', 'Verpine Prototype Shield',
          'Cinnagar War Suit', 'Advanced Stabilizer Gloves'],
 'action': ['Adrenal Strength (Self)', 'Energy Shield (Self)', 'Master Critical Strike'],
 'actiondesc': ['Adrenal Strength\n(SELF)', 'Energy Shield\n(SELF)'],
 'target': ['Czerka Corporation Protocol Officer', 'Malak'],
 'xp': ['Experience Points (XP) Received: 9999'],
 'credits': ['Credits Received: 999999', 'Credits Lost: 999999'],
 'credits_value': ['9999999','2147483647','1888888888'],
 'xp_value': ['0,000,000','2,147,483,647','1,888,888,888'],
 'row': ['Experience Points (XP) Received: 9999', 'Advanced Stabilizer Gloves']}


def digest(data): return hashlib.sha256(data).hexdigest()
def size(path): return tuple(map(int, path.stem[4:].split('x')))
def size_name(wh): return f'{wh[0]}x{wh[1]}'

def outside_refusal(code, stderr):
    return code==2 and b'is outside the resolutions the sets cover' in stderr.lower()

def corpus_fingerprint(paths):
    manifest=[]; length=0
    for p in sorted(set(paths)):
        data=p.read_bytes(); length+=len(data)
        manifest.append(str(p.relative_to(ROOT))+'\0'+digest(data)+'\n')
    return {'bytes':length,'sha256':digest(''.join(manifest).encode())},len(manifest)

def run(cmd):
    result = subprocess.run(list(map(str, cmd)), capture_output=True, text=True)
    if result.returncode: raise RuntimeError(f'{cmd[0]} exited {result.returncode}: {result.stderr[-2000:]}')
    return result.stdout


def load_game(path):
    """Read packed core and module templates; never use installed Override as stock."""
    from pykotor.extract.installation import Installation
    logging.disable(logging.CRITICAL)
    with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        installation = Installation(path)
        resources = installation.core_resources()
        module_names=installation.modules_list()
        resources += [r for name in module_names for r in installation.module_resources(name)
                      if r.restype() in (ResourceType.UTI,ResourceType.UTC)]
    tlk = read_tlk(path / 'dialog.tlk')
    stock, items, actions, targets, inputs = {}, set(), set(), set(), {}
    stock_fonts = {}
    from build_scaled_fonts import FONT_RESREFS, raw_txi
    from pykotor.resource.formats.erf import read_erf
    textures = path / 'TexturePacks/swpc_tex_gui.erf'
    if textures.is_file():
        for resource in read_erf(textures):
            name = str(resource.resref).lower()
            if name in FONT_RESREFS: stock_fonts[name] = Font(raw_txi(bytes(resource.data)).encode('ascii'))
        inputs['TexturePacks/swpc_tex_gui.erf'] = {'bytes':textures.stat().st_size,'sha256':digest(textures.read_bytes())}
    for name in ('dialog.tlk', 'chitin.key'):
        p = path / name; inputs[name] = {'bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())}
    def localized(loc):
        if loc is None: return ''
        entry=tlk.get(loc.stringref)
        if entry is not None: return entry.text
        return str(loc) if loc.stringref<0 and len(loc)>0 else ''
    for resource in resources:
        typ = resource.restype()
        if typ in (ResourceType.GUI,ResourceType.UTI,ResourceType.UTC,ResourceType.TwoDA):
            source = Path(resource.filepath())
            name = str(source.relative_to(path))
            if name not in inputs:
                inputs[name] = {'bytes':source.stat().st_size,'sha256':digest(source.read_bytes())}
        if typ == ResourceType.GUI:
            stock[resource.resname().lower()+'.gui'] = nodes(resource.data())
        elif typ in (ResourceType.UTI, ResourceType.UTC):
            g = read_gff(resource.data()).root
            if typ==ResourceType.UTI:
                text=localized(g.acquire('LocalizedName',None))
            else:
                text=' '.join(t for t in (localized(g.acquire('FirstName',None)),
                                         localized(g.acquire('LastName',None))) if t)
            if text: (items if typ==ResourceType.UTI else targets).add(text)
        elif typ == ResourceType.TwoDA and resource.resname().lower() in ('baseitems','spells','feat'):
            table = read_2da(resource.data())
            for row in table:
                for key in ('name','Name','label'):
                    try: ref = int(row.get_string(key))
                    except (ValueError, KeyError): continue
                    entry = tlk.get(ref)
                    if entry and entry.text: (items if resource.resname().lower()=='baseitems' else actions).add(entry.text)
    candidates = {k:list(v) for k,v in FALLBACK.items()}
    if items: candidates['item'] = sorted(items)
    if actions: candidates['action'] = sorted(actions | items) + FALLBACK['action']
    if targets: candidates['target'] = sorted(targets)
    candidates['actiondesc'] += [name+'\n(SELF)' for name in candidates['action']
                                 if '\n' not in name and '\r' not in name]
    return stock, tlk, candidates, inputs, (len(items),len(actions),len(targets),len(module_names)), stock_fonts


def runtime_slot(gui,n):
    tag = n.tag.upper()
    if tag == 'LBL_ACTIONDESC': return 'actiondesc', 2
    if tag.endswith('BG') or 'BACKGROUND' in tag: return None
    if tag=='LBL_CREDITS_VALUE': return 'credits_value',1
    if gui=='character.gui' and tag in ('LBL_EXPERIENCE_STAT','LBL_NEEDED_XP'): return 'xp_value',1
    if tag in ('LBL_JOURNAL','LBL_CASH','LBL_PLOTXP','LBL_ITEMRCVD','LBL_ITEMLOST'): return None
    if tag=='LBL_NAME' and (gui.startswith('mipc') or gui in ('mi8x6.gui','maininterface.gui')): return 'target',1
    if tag=='LBL_NAME' and gui=='abilities.gui': return 'action',1
    if any(x in tag for x in ('ITEMNAME','ITEM_NAME')): return 'item',1
    if n.path.endswith('/PROTOITEM'):
        parent = n.path.rsplit('/', 2)[-2].upper()
        if any(part in parent for part in ('ITEM', 'INVENTORY', 'SHOP')): return 'item',1
        if any(part in parent for part in ('ABILITY', 'POWER', 'FEAT')): return 'action',1
    return None


class Audit:
    def __init__(self, args):
        self.args = args
        self.exceptions = json.loads(ALLOWLIST.read_text())['entries']
        for e in self.exceptions:
            if not e.get('reason') or not e.get('established'): raise ValueError('allowlist lacks provenance')
        self.findings = {}
        self.stats = Counter(); self.coverage = Counter(); self.notes = []
        self.candidates = FALLBACK; self.tlk = None; self.stock = {}; self.game_inputs = {}; self.stock_fonts = {}
        self.scaling = defaultdict(list); self.scale_rows = []
        self.longest = {}; self.runtime_lines = {}; self.source_rows = []; self.art_cache = {}; self.font_cache = {}
        self.archive_hashes = {}; self.references = {}; self.gold = {}
        self.reference_nodes = {}; self.comparisons = {}
        self.probes = []
        self.captions = {}
        if args.game:
            self.stock,self.tlk,self.candidates,self.game_inputs, counts,self.stock_fonts = load_game(args.game)
            self.notes.append(f'Game read: {len(self.stock)} stock GUIs; {counts[0]} distinct item names, '
                              f'{counts[1]} action names, {counts[2]} creature names; {counts[3]} module capsules scanned. '
                              'Core KEY/BIF, Patch.erf and module UTI/UTC templates read. User-created names, '
                              'save/placed-object overrides and installed Override modifications remain untested.')
            self.notes.append(f'{len(self.stock_fonts)} stock fonts read from the game GUI texture pack for text inheritance comparisons.')
        else:
            self.notes.append('UNTESTED game GUI/TLK/item templates: --game not supplied; documented fallback names used.')
        self.notes.append('Audit correction from the initial 2026-10-02 run: runtime-label matching also assigned '
                          'action text to LBL_ACTIONDESCBG; that was an invalid slot assumption. The final run restricts '
                          'that slot to LBL_ACTIONDESC. The initial run evaluated upstream text with enlarged KMRP fonts; '
                          'that established shared geometry, not inherited clipping. The final run uses stock embedded TXI '
                          'metrics for text inheritance when available; otherwise text inheritance is untested and conservative KMRP.')
        self.notes.append('Blend classification correction: failing contributing anchors alone do not establish '
                          'inheritance at the target size. The final run independently interpolates unmodified upstream '
                          'EXTENTs at the native table weights, rounds once half away from zero, and checks that '
                          'same-size reference. Incompatible/nonconstant reference fields leave inheritance untested and KMRP.')
        self.notes.append('Runtime-slot correction: HUD notification icons and static Credits/Experience captions '
                          'are not the status-summary lines. Numeric credits/XP values use their own corpus; '
                          'the signed-32-bit upper-bound samples are explicit assumptions, not measured game caps. '
                          'Character/player-name slots and notification icon counters remain untested. Prototype '
                          'rows receive the real item corpus only for item/inventory/shop lists and the action corpus '
                          'only for ability/power/feat lists. Description, dialogue, option and module row contents '
                          'remain untested rather than being assigned an unrelated corpus.')
        self.notes.append('Overlap-triage correction: the first run compared every pair of sibling rectangles, '
                          'including decorative art, progress fills and status layers. The requested invariant is now '
                          'applied to separate buttons (including toggles), text-bearing labels and list boxes. '
                          'Matching art/background containment remains covered by its dedicated checks and allowlist.')
        self.notes.append('Corpus correction: a pykotor LocalizedString with a valid TLK reference and no inline '
                          'substring is false in a boolean test. The loader now tests presence with is not None '
                          'and resolves TLK references; it also includes module-local item/creature templates. '
                          'Action-description upper-bound probes append the known SELF line to the broad real '
                          'single-line item/action name corpus. Multiline template labels (including terminal text) '
                          'are excluded from that name-plus-SELF probe; their other corpus checks remain. '
                          'Which of those names is actually used in a SELF slot is untested; '
                          'these are conditional capacity findings, not observed gameplay assignments.')
        if self.tlk:
            from build_controller_prompt_textures import PROMPT_STRREFS
            for key,variants in PROMPT_STRREFS.items():
                texts=[]
                for refs in variants:
                    entries=[self.tlk.get(r) for r in refs]
                    if all(entries): texts.append(' '.join(e.text.strip() for e in entries))
                if texts: self.captions[key]=texts
        for p in sorted(UPSTREAM.glob('*/*/*.gui')):
            self.references[(p.parent.name.removeprefix('gui.'),p.name.lower())] = p
        for p in (ROOT/'assets/override-3440x1440').glob('*.gui'): self.gold[p.name.lower()] = nodes(p.read_bytes())

    def allowed(self, gui, tag, check, wh, amount):
        for e in self.exceptions:
            if (fnmatch.fnmatchcase(gui,e['gui']) and fnmatch.fnmatchcase(tag,e['tag'])
                and fnmatch.fnmatchcase(check,e['check']) and
                (not e.get('sizes') or size_name(wh) in e['sizes']) and
                amount <= e.get('max_amount',float('inf'))): return e
        return None

    def emit(self, gui, tag, check, wh, amount, detail, ref=None, scope='panel', forced=None):
        if amount <= .01: return
        e = self.allowed(gui,tag,check,wh,amount)
        cls = forced or ('by design' if e else 'inherited' if ref and (tag,check) in ref else 'KMRP')
        key = (scope,gui,tag,check,cls)
        if key not in self.findings:
            self.findings[key] = {'sizes':set(), 'worst':(-1,''), 'detail':'',
                                  'reason':e['reason']+'; '+e['established'] if e else
                                  'Same invariant fails in the comparison file at this size/ratio.' if cls=='inherited' else
                                  'No failing same-size/ratio reference established; requires maintainer review.'}
        row = self.findings[key]; row['sizes'].add(size_name(wh))
        if amount > row['worst'][0]:
            row['worst'] = (amount,size_name(wh)); row['detail'] = detail
            if cls=='inherited' and (gui,size_name(wh)) in self.comparisons:
                row['detail']+='; comparison='+self.comparisons[gui,size_name(wh)]

    def font_set(self, archive):
        fonts = {}
        for name in archive.namelist():
            if not name.lower().endswith('.txi'): continue
            data = archive.read(name)
            if b'fontheight' not in data.lower(): continue
            sha = digest(data)
            if sha not in self.font_cache: self.font_cache[sha] = Font(data)
            fonts[Path(name).stem.lower()] = self.font_cache[sha]
        return fonts

    def badges(self, wh, table, read, scope, guis):
        from build_controller_prompt_textures import PROMPT_TARGETS
        by_resref={t.resref:t for t in PROMPT_TARGETS}
        for badge in table[5]:
            base='kmrp'+badge['resref'][4:]
            target=by_resref.get(base) or by_resref[base.rstrip('0123456789')]
            control=next(c for c in guis[badge['gui']].children if c.tag==target.tag)
            w,h=control.rect[2:]
            tga=read(badge['resref']+'.tga'); tw,th=struct.unpack_from('<HH',tga,12)
            if badge['backing'] is None:
                alpha=tga[21:18+tw*th*4:4]
            else:
                r,g,b,a=badge['backing']; backing=bytes((b,g,r,a))
                pixels=tga[18:18+tw*th*4]
                alpha=bytes(pixels[i:i+4]!=backing for i in range(0,len(pixels),4))
            rows=[alpha[y*tw:(y+1)*tw] for y in range(th)]
            drawn=[r for r in rows if r.strip(b'\0')]
            if drawn and h:
                left=min(len(r)-len(r.lstrip(b'\0')) for r in drawn)
                right=max(len(r.rstrip(b'\0')) for r in drawn)
                aspect=((right-left)*w/tw)/(len(drawn)*h/th)
                self.emit(badge['gui'],badge['resref'],'badge aspect',wh,max(0,abs(aspect-1)-.06)*100,
                          f'alpha aspect={aspect:.4f}; 6% tolerance; excess percentage points',scope=scope)
                self.stats['badge cases']+=1

    def known(self,n):
        if self.tlk and n.strref not in (-1,4294967295):
            e = self.tlk.get(n.strref)
            if e: return e.text
        return n.text

    @staticmethod
    def is_text_check(check):
        return (check.startswith(('text ','runtime ','single line','unbreakable')) or check=='font missing')

    def reference_failures(self, gui, root, wh, fonts):
        geometry={(p,c) for p,c,a,d in self.measurements(gui,root,wh,fonts) if not self.is_text_check(c)}
        if self.stock_fonts:
            geometry.update((p,c) for p,c,a,d in self.measurements(gui,root,wh,self.stock_fonts) if self.is_text_check(c))
        return geometry

    def probe(self, gui, root, wh, fonts):
        if gui!='mipc28x6.gui' or wh not in {
                (800,600),(1024,576),(1920,540),(1920,1200),(1036,583),(1077,606)}: return
        n=next((n for n in flatten(root) if n.tag=='LBL_ACTIONDESC'),None)
        if n and n.font in fonts:
            f=fonts[n.font]
            self.probes.append((size_name(wh),n.font,f.height,n.rect[2],n.rect[3],3*f.height-n.rect[3]))

    def measurements(self, gui, root, wh, fonts):
        """Return every failure; no findings are suppressed here."""
        failures = []
        out = lambda n,c,a,d: failures.append((n.path,c,float(a),d)) if a > .01 else None
        all_nodes = list(flatten(root)); tags = {n.tag:n for n in all_nodes}
        def visit(n, parent=None, relation='control'):
            x,y,w,h = n.rect
            if parent:
                # Embedded prototypes retain authored template coordinates. Report the literal
                # comparison and allow only documented exceptions, rather than rewriting them.
                bounds = (0,0,parent.rect[2],parent.rect[3])
                out(n,'containment',overshoot(n.rect,bounds),f'{n.rect} outside parent {parent.tag} {bounds}; relation={relation}')
            out(n,'positive extent', max(0,-w,-h),str(n.rect))
            if n.font:
                self.coverage['font controls'] += 1
                f = fonts.get(n.font)
                if f is None: out(n,'font missing',1,f'{n.font}.txi unavailable in nearest set')
                else:
                    effective_h = h
                    if relation=='PROTOITEM':
                        effective_h = h if gui=='optfeedback.gui' and parent.tag=='LB_OPTIONS' else row_height(h,wh[1])
                    out(n,'text one line', f.height-effective_h,
                        f'box={effective_h:g}px; line={f.height:g}px; font={n.font}')
                    text = self.known(n)
                    width = w
                    if n.kind==11: width -= (n.bar.rect[2] if n.bar else 0)+2*n.border+n.padding
                    if text:
                        self.coverage['known strings'] += 1
                        lines = f.wrap(text,max(1,width))
                        out(n,'text height',len(lines)*f.height-effective_h,
                            f'{len(lines)} lines * {f.height:g}px in {width:g}x{effective_h:g}; strref={n.strref}')
                        # Type 6 buttons and caption/title tags. Description labels remain multiline.
                        single = n.kind==6 or any(k in n.tag.upper() for k in ('TITLE','CAPTION','TAB'))
                        if single: out(n,'single line width',max(f.width(t) for t in text.splitlines())-width,
                                       f'font={n.font}; measured single-line advance; strref={n.strref}')
                        out(n,'unbreakable word',max((f.width(t) for t in text.split()), default=0)-width,
                            f'word exceeds {width:g}px; engine only wraps at spaces')
                    else: self.coverage['unresolved/empty text'] += 1
                    if (gui,n.tag) in self.captions:
                        captions=self.captions[gui,n.tag]
                        out(n,'runtime caption width',max(map(f.width,captions))-width,
                            f'PROMPT_STRREFS variants={captions!r}; width={width:g}; font={n.font}')
                        self.coverage['runtime caption controls']+=1
                    slot = runtime_slot(gui,n)
                    if slot:
                        category, expected = slot
                        texts = self.candidates[category]
                        cachekey = (id(f),category)
                        if cachekey not in self.longest:
                            self.longest[cachekey] = max(texts,key=f.width)
                        sample = self.longest[cachekey]
                        heightkey = (id(f),category,width)
                        if heightkey not in self.runtime_lines:
                            self.runtime_lines[heightkey] = max(
                                ((len(f.wrap(t,max(1,width))),t) for t in texts),key=lambda p:p[0])
                        linecount, height_sample = self.runtime_lines[heightkey]
                        needed = max(expected,linecount)
                        out(n,'runtime text height',needed*f.height-effective_h,
                            f'{category}: {needed} lines at {f.height:g}px; {width:g}x{effective_h:g}; sample={height_sample!r}')
                        if expected==1: out(n,'runtime single line width',f.width(sample)-width,
                                           f'{category}: longest glyph advance={f.width(sample):.3f}px; box={width:g}px; sample={sample!r}')
                        self.coverage['runtime slots'] += 1
            # Fixed aspect inferred only for semantically identified portraits/icons/hex art.
            if w>0 and h>0 and (re.search(r'(PORTRAIT|ICON|HEX|LBL_CHAR\d|LBL_(?:ACTION|TARGET)\d)',n.tag,re.I)):
                art_aspect = 1.0
                if n.art and n.art in self.art_cache: art_aspect = self.art_cache[n.art]
                deviation = abs((w/h)/art_aspect-1)
                self.coverage['fixed aspect controls'] += 1
                out(n,'art aspect',max(0,deviation-.06)*100,
                    f'extent aspect={w/h:.4f}, asset/reference aspect={art_aspect:.4f}; 6% tolerance; excess percentage points')
            if n.proto:
                row = n.proto.rect[3] if gui=='optfeedback.gui' and n.tag=='LB_OPTIONS' else row_height(n.proto.rect[3],wh[1])
                if (gui,n.tag) in ROW_LISTS: row = row_height(ROW_LISTS[gui,n.tag][1][0],wh[1])
                inner = h-2*n.border
                if row>0:
                    rows = inner//row
                    out(n,'list row fit',row-inner if rows<1 else 0,f'inner={inner}px, engine row={row}px')
                    # Whole rows plus integer shared gap: arbitrary remainders are permitted by
                    # OrganizeControls. Check the fitted popup pitch, not inner % row == 0.
                    if (gui,n.tag) in ROW_LISTS and ROW_LISTS[gui,n.tag][0]=='popup':
                        want = rows*(row+row//11)
                        out(n,'list fitted pitch',abs(inner-want),f'inner={inner}; {rows} rows at pitch {row+row//11}; want={want}')
            if n.bar:
                bx,by,bw,bh = n.bar.rect
                # SCROLLBAR coords are authored in the panel's space. Convert to list-local.
                local = (bx-x,by-y,bw,bh)
                out(n.bar,'scrollbar inside',overshoot(local,(0,0,w,h)),f'panel coords {n.bar.rect}; list={n.rect}')
                if bw>0:
                    side = min(abs(bx-x),abs(bx+bw-x-w))
                    out(n.bar,'scrollbar side',side-2,f'side distance={side}px; list={n.rect}; bar={n.bar.rect}')
            for c in n.children: visit(c,n)
            if n.proto: visit(n.proto,n,'PROTOITEM')
            if n.bar: visit(n.bar,n,'SCROLLBAR')
            # The requested overlap invariant concerns separate buttons, text labels and list
            # boxes. Decorative/art labels, progress fills and other drawing layers are not
            # independent overlap subjects. Toggle buttons (type 7) are buttons here.
            def overlap_subject(control):
                if control.kind in (6, 7, 11): return True
                if control.kind not in (4, 5) or not control.font: return False
                return bool(self.known(control) or runtime_slot(gui,control) or
                            (gui,control.tag) in self.captions)
            siblings = [control for control in n.children if overlap_subject(control)]
            for i,a in enumerate(siblings):
                for b in siblings[i+1:]:
                    hit = overlap(a.rect,b.rect)
                    if hit: out(a,'overlap:'+b.path,hit,f'{a.tag} {a.rect} intersects {b.tag} {b.rect}; minimum penetration')
        visit(root)
        active = 'mipc210x7.gui' if wh==(3440,1440) else 'mipc28x6.gui'
        hud = gui.startswith('mipc') or gui in ('mi8x6.gui','maininterface.gui')
        full = root.rect[2:]==wh
        if full or hud:
            for n in all_nodes:
                if n is root or '/' not in n.path.removeprefix('root/'): # direct controls only; nested handled by containment
                    out(n,'screen edge',overshoot(n.rect,(0,0,*wh)),f'{n.rect} vs screen {wh}')
        if hud and 'LBL_NAME' in tags:
            edge = tags['LBL_NAME'].rect[0]+tags['LBL_NAME'].rect[2]
            for tag,n in tags.items():
                if re.match(r'(BTN|LBL)_TARGET(?:UP|DOWN)?\d$',tag):
                    out(n,'target clip edge',n.rect[0]+n.rect[2]-edge,f'right={n.rect[0]+n.rect[2]}; LBL_NAME right={edge}')
        # Logical layered controls must stay inside their corresponding drawing slots.
        for tag,n in tags.items():
            partner = None
            if re.match(r'LBL_(ACTION|TARGET)\d$',tag): partner = tags.get(tag.replace('LBL_','BTN_'))
            if tag+'BG' in tags: partner = tags.get(tag+'BG')
            if partner:
                out(n,'drawn containment',overshoot(n.rect,partner.rect),f'{n.rect} inside {partner.tag} {partner.rect}')
        return failures

    def process(self, gui, data, wh, fonts, reference=None, listed=False):
        root = nodes(data)
        hud = gui.startswith('mipc') or gui in ('mi8x6.gui','maininterface.gui')
        scope = 'active HUD' if gui==('mipc210x7.gui' if wh==(3440,1440) else 'mipc28x6.gui') else 'unused HUD' if hud else 'panel'
        self.stats['files'] += 1; self.stats['controls'] += sum(1 for _ in flatten(root))
        failures = self.measurements(gui,root,wh,fonts)
        self.probe(gui,root,wh,fonts)
        ref = None
        if reference:
            ref = self.reference_failures(gui,reference,wh,fonts)
        elif gui in self.stock:
            stock = self.stock[gui]
            # A stock comparison is restricted to aspect invariants; raw 640x480 coordinates
            # cannot establish same-size clipping or overlap.
            ref = {(p,c) for p,c,a,d in self.measurements(gui,stock,(640,480),fonts) if c=='art aspect'}
        for tag,check,amount,detail in failures: self.emit(gui,tag,check,wh,amount,detail,ref,scope)
        if listed:
            for n in flatten(root): self.scaling[gui,n.path].append((*wh,n.rect))
        return root

    def runtime(self, wh, fonts, guis):
        font = fonts.get('dialogfont16x16')
        if font:
            # All 1..9 visible summary rows; actual font assignment is a runtime assumption.
            texts = self.candidates['xp']+self.candidates['credits']
            widest = max(map(font.width,texts))
            for count in range(1,10):
                p, rows, ok = status_summary(*wh,font,widest,count)
                self.emit('[status_summary]','panel','screen edge',wh,overshoot(p,(0,0,*wh)),f'{count} rows; panel={p}',scope='runtime model')
                for i,r in enumerate(rows):
                    self.emit('[status_summary]',f'line{i}','text width',wh,widest-r[2],f'advance={widest:.3f}; line={r}',scope='runtime model')
                    self.emit('[status_summary]',f'line{i}','containment',wh,overshoot(r,(0,0,p[2],p[3])),str(r),scope='runtime model')
                self.emit('[status_summary]','OK','containment',wh,overshoot(ok,(0,0,p[2],p[3])),str(ok),scope='runtime model')
                self.stats['summary cases'] += 1
        if 'confirm.gui' in guis:
            r = guis['confirm.gui']; n = next((c for c in r.children if c.tag=='LB_MESSAGE'),None)
            f = fonts.get(n.proto.font if n and n.proto and n.proto.font else n.font if n else '')
            if f:
                for text in ('Do you really want to quit?', 'The attributes of your character apply bonuses to your skills and abilities.'):
                    for shown in ((True,False,False),(True,True,False),(True,False,True),(True,True,True)):
                        fitted = popup_fit(r,f,text,*shown)
                        self.stats['popup cases'] += 1
                        if fitted:
                            panel, children = fitted
                            for tag,rect in children:
                                self.emit('[popup_fit]',tag,'containment',wh,overshoot(rect,(0,0,panel[2],panel[3])),str(rect),scope='runtime model')
                            self.emit('[popup_fit]','panel','screen edge',wh,overshoot(panel,(0,0,*wh)),str(panel),scope='runtime model')
        if 'skillinfo.gui' in guis:
            for count in range(1,11):
                panel, children, geometry = granted_fit(guis['skillinfo.gui'],wh[1],count)
                for tag,rect in children:
                    self.emit('[granted_popup]',tag,'containment',wh,overshoot(rect,(0,0,panel[2],panel[3])),f'{count} granted; {rect}',scope='runtime model')
                self.emit('[granted_popup]','panel','screen edge',wh,overshoot(panel,(0,0,*wh)),str(panel),scope='runtime model')
                self.stats['granted cases'] += 1

    def scaling_checks(self):
        rules = {}
        for (gui,tag),points in sorted(self.scaling.items()):
            wx,wr = scaling_rule(points,2); hy,hr = scaling_rule(points,3)
            rules[gui,tag] = (wx,hy)
            self.scale_rows.append((gui,tag,wx,hy,wr,hr))
        # Every numbered family (buttons, arrows, icons, backgrounds) compared, including combat queue.
        families = defaultdict(list)
        for key,rule in rules.items():
            gui,tag=key; canonical = re.sub(r'\d+','#',tag)
            families[gui,canonical].append((tag,rule))
        for (gui,family),members in families.items():
            if len(members)>1 and len({rule for _,rule in members})>1:
                for tag,rule in members:
                    for w,h,rect in self.scaling[gui,tag]:
                        self.emit(gui,tag,'scaling family', (w,h),1,
                                  f'{family}: '+', '.join(f'{t}={r}' for t,r in members),scope='scaling model')
        # Cross-tag semantic HUD families, documented in apply_gold_hud_proportions.
        from apply_gold_hud_proportions import BOTTOM_LEFT_TAGS, BOTTOM_RIGHT_TAGS, TARGET_BUTTON_TAGS
        groups = {'party HUD':BOTTOM_LEFT_TAGS, 'action HUD':BOTTOM_RIGHT_TAGS,
                  'target buttons':TARGET_BUTTON_TAGS,
                  'combat queue':tuple(f'{prefix}{i}' for i in range(6)
                                       for prefix in ('LBL_COMBATBG','BTN_CLEAR','LBL_QUEUE','LB_ACTIONS'))}
        for gui in {g for g,t in rules if g.startswith('mipc')}:
            for group,tags in groups.items():
                members=[(t,rules[gui,'root/'+t]) for t in tags if (gui,'root/'+t) in rules]
                if len({r for t,r in members}) > 1:
                    for tag,rule in members:
                        for w,h,rect in self.scaling[gui,'root/'+tag]:
                            self.emit(gui,'root/'+tag,'scaling group',(w,h),1,
                                      group+': '+', '.join(f'{t}={r}' for t,r in members),scope='scaling model')

    def source_checks(self):
        def body(path, signature):
            text = (ROOT/path).read_text(); start = text.index(signature)
            opening = text.index('{',start); depth=1; end=opening+1
            while depth:
                depth += (text[end]=='{')-(text[end]=='}'); end+=1
            return text[opening:end]
        checks = [
            ('Mac focus requires Selectable', 'Selectable(hud, active)' in body('macos/patches/kmrp-controller/hud.cpp','bool ActionBarFocused()')),
            ('Mac activate requires Selectable', bool(__import__('re').search(r'pending\.activate\s*&&\s*active\s*>=\s*0\s*&&\s*Selectable\(hud, active\)',(ROOT/'macos/patches/kmrp-controller/hud.cpp').read_text()))),
            ('Windows focus requires selectable action', 'IsActionButtonSelectable(' in body('src/controller-native/vendor/K1XboxControls.cpp','bool IsActionBarFocused(')),
            ('Windows core frame calls StatusSummaryFrameK1', 'StatusSummaryFrameK1(guiManager)' in body('src/controller-native/K1NativeJoystick.cpp','extern "C" void __cdecl CoreGuiFrameK1('))]
        for name,ok in checks:
            self.source_rows.append((name,ok)); print(f'{"ok  " if ok else "FAIL"} source gate: {name} (source inspection; untested in game)')
            if not ok: self.emit('[source]',name,'gate',(0,0),1,'source predicate absent',scope='source')

    def mac_build(self, tmp):
        if platform.system()!='Darwin':
            self.notes.append('UNTESTED Mac binary builds: host is not macOS.'); return
        kpm=ROOT/'third_party/Kotor-Patch-Manager'
        args=[sys.executable, ROOT/'macos/tools/make_kmrp_patch.py',
              '--widescreen',kpm/'Patches/K1WidescreenPatch','--stray',kpm/'Patches/K1StrayBugFixes',
              '--layout',ROOT/'macos/patches/kmrp-layout','--notes',ROOT/'macos/patches/kmrp-map-notes',
              '--notes-include',ROOT/'build/macos/map-notes','--controller',ROOT/'macos/patches/kmrp-controller',
              '--sdl',ROOT/'build/deps/SDL3-3.4.16-macos','--version',(ROOT/'macos/VERSION').read_text().strip()]
        for disabled in (False,True):
            label='without controller' if disabled else 'with controller'
            artifact=tmp/f'mac-{disabled}.kpatch'
            try:
                run([*args,*(['--no-controller'] if disabled else []),'--out',artifact])
                with zipfile.ZipFile(artifact) as z:
                    hookname=next(n for n in z.namelist() if n.endswith('.hooks.toml'))
                    hooks=tomllib.loads(z.read(hookname).decode())
                    frame=[h for h in hooks['hooks'] if h.get('address')==0x10049f636]
                    symbol='KmrpCoreGuiFrame' if disabled else 'KmrpGuiFrame'
                    module=tmp/f'module-{disabled}.dylib'; data=z.read('binaries/macos_x86_64.dylib'); module.write_bytes(data)
                    exports=run(['nm','-gU',module])
                    ok=(len(frame)==1 and frame[0]['function']==symbol and
                        '_'+symbol in exports.split() and '_KmrpCoreGuiFrame' in exports.split())
                    self.notes.append(f'Mac rebuilt {label}: .kpatch SHA-256 {digest(artifact.read_bytes())}; '
                                      f'module {len(data)} bytes SHA-256 {digest(data)}. VA 0x10049f636 -> {frame}; '
                                      'nm -gU checked KmrpCoreGuiFrame export. VA is hook metadata, not a file offset.')
                    print(f'{"ok  " if ok else "FAIL"} Mac built artifact {label}: GUI frame VA 0x10049f636 -> {symbol}; core export')
                    if not ok: self.emit('[build]',label,'GUI frame',(0,0),1,str(frame),scope='build')
            except (RuntimeError,KeyError,StopIteration) as error:
                print(f'FAIL Mac built artifact {label}: {error}')
                self.emit('[build]',label,'build',(0,0),1,str(error),scope='build')
        self.notes.append('UNTESTED Windows compiled no-controller module and GuiBlend.cs execution on this Mac; '
                          'Windows source stand-in checked separately. Run Test-GuiBlendHelper.py on Windows for compiled C# parity.')

    def report(self):
        corpora={
            'Upstream GUI corpus':UPSTREAM.rglob('*.gui'),
            '3440x1440 gold GUI corpus':(ROOT/'assets/override-3440x1440').glob('*.gui'),
            'Audit/build/formula source corpus':[
                Path(__file__),Path(__file__).with_name('gui_audit_model.py'),ALLOWLIST,
                Path(__file__).with_name('Test-GuiBlendHelper.py'),Path(__file__).with_name('Test-GeneratedGuiGeometry.py'),
                ROOT/'tools/build_gui_blend_table.py',ROOT/'tools/derive_resolution_gui_set.py',
                ROOT/'tools/build_scaled_fonts.py',ROOT/'tools/build_controller_prompt_textures.py',
                ROOT/'tools/scale_listbox_padding.py',ROOT/'tools/scale_message_popup.py',
                ROOT/'macos/tools/kmrp-guiblend.c',ROOT/'macos/tools/make_kmrp_patch.py',
                *(ROOT/'macos/patches').rglob('*.cpp'),*(ROOT/'macos/patches').rglob('*.h'),
                *(ROOT/'macos/patches').rglob('*.toml'),ROOT/'src/controller-native/K1ControllerLayout.cpp',
                ROOT/'src/controller-native/K1NativeJoystick.cpp',ROOT/'src/controller-native/vendor/K1XboxControls.cpp',
                ROOT/'src/patcher/GuiBlend.cs']}
        for label,paths in corpora.items():
            fingerprint,count=corpus_fingerprint(paths);self.game_inputs[label]=fingerprint
            self.notes.append(f'{label}: {count} files; corpus SHA-256 uses sorted repository-relative '
                              'path + NUL + each file SHA-256 + newline, encoded UTF-8; Bytes is the summed length.')
        counts=Counter(key[-1] for key in self.findings)
        lines=['# GUI audit — '+self.args.date,'',
               'Lab record. Computed from packaged GFF/TXI/TGA bytes and freshly generated native blends. '
               'No game execution or visual play-test was performed. Layouts and resource generators were not changed. '
               'See [documentation standard](../docs/documentation-standard.md).','',
               '## Run and build identity','',
               'Command: `'+(subprocess.list2cmdline([sys.executable,*sys.argv]) if os.name=='nt'
                             else shlex.join([sys.executable,*sys.argv]))+'`','',
               f'Repository HEAD: `{run(["git","-C",ROOT,"rev-parse","HEAD"]).strip()}`; worktree changes are listed below. '
               'Hashes identify inputs; these are local build outputs, not a released-build assertion.','',
               '```text',run(['git','-C',ROOT,'status','--short']).strip(),'```','',
               f'Measured {self.stats["listed sizes"]} listed sizes and {self.stats["blend sizes"]} blended sizes; '
               f'{self.stats["rejected sizes"]} native-helper rejections; {self.stats["files"]} GUI instances; '
               f'{self.stats["controls"]} control instances including roots, prototypes and scrollbars.','',
               f'Finding groups: KMRP {counts["KMRP"]}; inherited {counts["inherited"]}; by design {counts["by design"]}. '
               'Each group is scoped by active HUD / unused HUD / panel / runtime / source / build, '
               'then GUI, recursive control path, check and class; size counts are unique within a group.','',
               '## Method, formulas and limits','',
               '- Height: `fontheight * 100`; glyph advance: `(lower.x-upper.x) * texturewidth * 100`, '
               'plus `spacingR * 100` between glyphs. TXI comes from the same listed set or nearest-by-height-then-aspect set. '
               'CP1252 encoding is an assumption for the English game strings. Space wrapping retains unbreakable words; '
               'overflow means top lines are dropped and the last remains under Stray K5.',
               '- Children are panel-relative. Literal prototype containment is reported, but documented template-coordinate '
               'exceptions are classified through the data allowlist. Scrollbars get both a literal local-space check '
               'and the panel-space conversion; their runtime placement beyond these hypotheses is untested.',
               '- Intersections between sibling buttons (including toggles), text-bearing labels and list boxes are '
               'reported as minimum-axis penetration in pixels. Decorative art, progress fills and other drawing layers '
               'are not independent overlap subjects; their matching containment/aspect checks still apply. Explicit '
               'background layers are listed in the allowlist with upstream evidence. Visibility/state exclusivity not '
               'established by those entries remains a finding; rectangle intersection alone does not prove simultaneous visibility.',
               '- Fixed aspect checks use identified portrait/icon/hex tags and TGA dimensions when available; '
               'otherwise square is an explicitly modelled assumption. Six percent tolerance allows integer rounding. '
               'All badge variants are checked; opaque-backed badges isolate the drawing by subtracting the known '
               'constant backing color from TGA pixels. '
               'TPC-only art, animation frames, opaque painted borders and readable contrast remain untested.',
               '- Scaling uses every equal-width/different-height and equal-height/different-width pair: fit fixed, '
               '`max(1,H/720)`, width or per-axis dimensions, with 6% ratio residual. Numbered siblings with differing '
               'rules are flagged. This model does not prove a semantic group is supposed to share a rule.',
               '- Runtime slots are identified by tags/prototype role. Longest means largest glyph advance per font, '
               'not character count. Action description has a documented two-line name plus `(SELF)` case. Arbitrarily long '
               'player/mod names cannot be bounded by this corpus. Empty/unknown runtime slots remain untested.',
               '- Status summary: `at16(v)=(v*lineHeight+8)//16`, line x=at16(52), width=widest+lineHeight//4, '
               'screen cap and roomy OK rule, row pitch=at16(37), y=at16(10), OK y=y-at16(7), panel height=OK y+at16(32). '
               'All 1..9 rows checked; dialogfont16x16 assignment is an assumption, not a runtime measurement.',
               '- Popup fit reproduces minimum-width bisection preserving wrapped height, shrink-to-text, buttons '
               '4/2 px below, and saved-message-top bottom margin, all icon/OK/Cancel visibility combinations. '
               'Engine list-inner/item-height queries are modelled from border/padding/TXI, untested in game.',
               '- Granted popup: row=round(float32(50*max(1,float32(H/720)))), visible=min(count,inner//row), '
               'want=visible*(row+row//11), cut only if native visible count remains equal; OK/panel move by cut. '
               'Hex grows by row//7; text insets row//8. Counts 1..10 checked.',
               '- List rows use prototype height times the engine scale; Feedback checkbox template is already scaled. '
               'Real runtime names are checked only for item/inventory/shop and ability/power/feat prototypes; other '
               'row contents remain untested. Code-row lists use ROW_LISTS bases. Whole rows include integer shared gaps; requiring '
               '`inner % row == 0` was rejected because OrganizeControls intentionally distributes slack. '
               'Fitted popup pitch is checked exactly; source/runtime row class assignment for other lists is untested.',
               '- Blends compare each emitted varying int32 against the convex range of contributing anchors, '
               'with 1 px rounding tolerance. Post-fit widening, fitted lists and generated Controller Layout extents '
               'can exceed that range and are retained as findings, not silently exempted. Shape blending can use '
               'four anchors rather than just two; all contributors are the correct bounds.',
               '- Classification: explicit allowlist -> by design; same-size upstream failing the same invariant -> '
               'inherited; otherwise KMRP pending review. Blend references independently interpolate unmodified '
               'upstream extents at the same contributing weights. Upstream text uses stock embedded TXI metrics when available; '
               'without them text inheritance is untested and remains KMRP. Stock 640x480 establishes '
               'aspect inheritance only; play-tested gold is reported as a reference, not automatic permission to hide faults.',
               '- Source gates are source-level checks, untested in game. Artifact hook metadata and exported symbols '
               'establish build wiring, not successful detouring in a live process. No executable bytes were modified.','',
               '## Coverage notes','',*['- '+n for n in self.notes],'',
               'Coverage counters include comparison-file measurements as well as tested outputs:','',
               '| Kind | Count |','| --- | ---: |',* [f'| {k} | {v} |' for k,v in sorted(self.coverage.items())],'',
               'Runtime cases: '+', '.join(f'{k}={v}' for k,v in self.stats.items() if 'cases' in k)+'.','',
               '## Reported action-description probes','',
               'These are numeric three-line capacity checks, not a play-test of the last-line rendering.','',
               '| Size | Font | Line height | Width | Box height | Three-line shortfall |',
               '| --- | --- | ---: | ---: | ---: | ---: |',
               *[f'| {s} | {f} | {lh:g} | {w} | {h} | {short:g} |' for s,f,lh,w,h,short in self.probes], '',
               '## Findings','',
               '| Scope | GUI | Control / pair | Check | Class | Sizes | Worst size | Amount | Evidence / reason |',
               '| --- | --- | --- | --- | --- | ---: | --- | ---: | --- |']
        clean=lambda t:str(t).replace('|','\\|').replace('\n',' / ').replace('\r','')
        for key,row in sorted(self.findings.items()):
            scope,gui,tag,check,cls=key
            evidence=row['detail']+'; '+row['reason']
            if gui in self.gold:
                gold={n.path:n for n in flatten(self.gold[gui])}
                if tag in gold: evidence+=f'; 3440x1440 gold rect={gold[tag].rect}'
            lines.append('| '+' | '.join(map(clean,(scope,gui,tag,check,cls,len(row['sizes']),row['worst'][1],
                                                   f'{row["worst"][0]:.3f}',evidence)))+' |')
        lines += ['', '## Scaling classification (every listed control)','',
                  '| GUI | Control | Width rule | Height rule | Width residual | Height residual |',
                  '| --- | --- | --- | --- | ---: | ---: |']
        lines += ['| '+' | '.join(map(clean,(g,t,w,h,f'{wr:.4f}',f'{hr:.4f}')))+' |' for g,t,w,h,wr,hr in self.scale_rows]
        lines += ['', '## Allowlist (data; each exception retained in findings)','',
                  '| GUI | Control / pair | Check | Reason | Established |','| --- | --- | --- | --- | --- |']
        lines += ['| '+' | '.join(clean(e[k]) for k in ('gui','tag','check','reason','established'))+' |' for e in self.exceptions]
        lines += ['', '## Input hashes','', '| Input | Bytes | SHA-256 |', '| --- | ---: | --- |']
        lines += [f'| {name} | {data["bytes"]} | `{data["sha256"]}` |' for name,data in sorted({**self.archive_hashes,**self.game_inputs}.items())]
        lines += ['', '## Reproduce and inspect by hand','',
                  'Run the command above with the project venv. A nonzero exit with KMRP findings is expected until '
                  'the maintainer reviews them. Do not add blanket exemptions to make it green. Open the worst-size '
                  'archive, read the named control EXTENT and its font TXI, and recompute the formula above. '
                  'For blends, build gui-blend.bin and kmrp-guiblend as Test-GuiBlendHelper.py does, choose the nearest '
                  'font set, and read the same fields from its output. For Mac wiring, inspect the rebuilt .kpatch '
                  'hook TOML at VA 0x10049f636 and run `nm -gU` on its dylib. '
                  'Live render, focus, wrapping, popup fitting and Windows compiled configuration remain untested '
                  'until independently exercised. No layouts, installed game files, commits or pushes were changed.','']
        self.args.report.parent.mkdir(parents=True,exist_ok=True)
        self.args.report.write_text('\n'.join(lines))
        return counts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resources',type=Path,nargs='?',default=ROOT/'build/kmrp/resources')
    parser.add_argument('--game',type=Path,help='game data directory containing chitin.key and dialog.tlk (optional)')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--date',default=date.today().isoformat())
    parser.add_argument('--listed-only',action='store_true',help='quick run; blend sweep explicitly untested')
    parser.add_argument('--skip-build',action='store_true',help='quick run; Mac artifacts explicitly untested')
    args=parser.parse_args(); args.resources=args.resources.resolve()
    args.report=(args.report or ROOT/'testing'/f'GuiAudit-{args.date}.md').resolve()
    audit=Audit(args)
    spec=importlib.util.spec_from_file_location('blend_test',Path(__file__).with_name('Test-GuiBlendHelper.py'))
    blend=importlib.util.module_from_spec(spec); spec.loader.exec_module(blend)
    geometry_spec=importlib.util.spec_from_file_location('geometry_test',Path(__file__).with_name('Test-GeneratedGuiGeometry.py'))
    geometry=importlib.util.module_from_spec(geometry_spec); geometry_spec.loader.exec_module(geometry)
    archives=sorted(args.resources.glob('gui-*.zip'),key=size)
    if len(archives)!=geometry.EXPECTED_ARCHIVE_COUNT:
        audit.emit('[archives]','count','expected',(0,0),abs(len(archives)-geometry.EXPECTED_ARCHIVE_COUNT),f'{len(archives)} vs {geometry.EXPECTED_ARCHIVE_COUNT}',scope='build')
    print(f'{"ok  " if len(archives)==geometry.EXPECTED_ARCHIVE_COUNT else "FAIL"} archives: {len(archives)} (expected {geometry.EXPECTED_ARCHIVE_COUNT})',flush=True)
    sets={}; fontsets={}; listed_sizes={size(p) for p in archives}
    with tempfile.TemporaryDirectory(prefix='kmrp-gui-audit-') as temp:
        tmp=Path(temp)
        tablepath=tmp/'gui-blend.bin';helper=tmp/'kmrp-guiblend'
        run([sys.executable,ROOT/'tools/build_gui_blend_table.py',args.resources,tablepath])
        if blend.native_helpers.WINDOWS:
            helper=blend.native_helpers.build(ROOT/'macos/tools/kmrp-guiblend.c',tmp,'kmrp-guiblend')['x64']
        else:run(['clang','-O2','-o',helper,ROOT/'macos/tools/kmrp-guiblend.c'])
        table=blend.read_table(tablepath)
        locations={name:field_locations(template) for name,template,offsets,values in table[4]}
        for archive in archives:
            wh=size(archive); res=size_name(wh)
            audit.archive_hashes[archive.name]={'bytes':archive.stat().st_size,'sha256':digest(archive.read_bytes())}
            with zipfile.ZipFile(archive) as z:
                fonts=audit.font_set(z); fontsets[wh]=fonts
                setdir=tmp/f'set-{res}';setdir.mkdir();sets[wh]=setdir
                # Helper reads captions/manifest only. Native generated art is audited separately.
                for name in blend.SET_FILES: (setdir/name).write_bytes(z.read(name))
                guis={}
                for name in sorted(z.namelist()):
                    if name.endswith('.tga'):
                        with z.open(name) as stream: hdr=stream.read(18)
                        if len(hdr)>=18:
                            w,h=struct.unpack_from('<HH',hdr,12)
                            if h: audit.art_cache[Path(name).stem]=w/h
                for name in sorted(z.namelist()):
                    if not name.endswith('.gui'):continue
                    p=audit.references.get((res,name))
                    if p is None and not any(r==res for r,n in audit.references):
                        try: p=geometry.upstream_gui(res,name)
                        except ValueError as error:
                            note=f'No same-size upstream reference at {res}: {error}. Findings without comparison remain KMRP pending review.'
                            if note not in audit.notes: audit.notes.append(note)
                    ref=nodes(p.read_bytes()) if p else None
                    if p:
                        audit.comparisons[name,res]=(str(p.relative_to(ROOT)) if p.is_relative_to(ROOT)
                                                    else 'derived upstream via derive_resolution_gui_set.py for '+res)
                    guis[name]=audit.process(name,z.read(name),wh,fonts,ref,True)
                audit.badges(wh,table,z.read,'listed badge',guis)
                audit.runtime(wh,fonts,guis)
            audit.stats['listed sizes']+=1
        print(f'ok   listed traversal: {audit.stats["listed sizes"]} sizes, {audit.stats["files"]} files, {audit.stats["controls"]} controls',flush=True)
        if not args.listed_only:
            audit.notes.append(f'Native helper table: {tablepath.stat().st_size} bytes, SHA-256 {digest(tablepath.read_bytes())}. '
                               'Sweep H=560..4400 inclusive step 23; width=round(H*aspect), six aspect families, '
                               'plus reported 1036x583 / 1077x606 cases. Listed duplicates skipped.')
            sizes=sorted({(round(h*a),h) for h in range(560,4401,23) for a in ASPECTS}|{(1036,583),(1077,606)})
            for wh in sizes:
                if wh in listed_sizes:continue
                nearest=min(listed_sizes,key=lambda s:(abs(s[1]-wh[1]),abs(s[0]/s[1]-wh[0]/wh[1])))
                out=tmp/'blend-output'
                result=subprocess.run([str(helper),str(tablepath),*map(str,wh),str(out),str(sets[nearest])],capture_output=True)
                if result.returncode:
                    if outside_refusal(result.returncode,result.stderr):
                        audit.stats['rejected sizes']+=1
                    else:
                        detail=f'exit={result.returncode}: '+result.stderr.decode(errors='replace').strip()
                        audit.emit('[guiblend]','native helper','generation',wh,1,detail,scope='build')
                        print(f'FAIL native helper {size_name(wh)}: {detail}',flush=True)
                    shutil.rmtree(out,ignore_errors=True);continue
                fonts=fontsets[nearest];guis={}
                terms=blend.terms_for(table[0],table[1],*wh)
                contributors=[(table[1][i][0],table[1][i][1]) for i,weight in terms]
                # Compare actual native output against every contributing anchor's actual int32 values.
                for name,template,offsets,values in table[4]:
                    data=(out/name).read_bytes()
                    for index,offset in enumerate(offsets):
                        v=struct.unpack_from('<i',data,offset)[0]
                        bounds=[values[i][index] for i,weight in terms]
                        amount=max(0,min(bounds)-v-1,v-max(bounds)-1)
                        if amount:
                            tag,field=locations[name].get(offset,(f'FILE {offset:#x}','unknown'))
                            audit.emit(name,tag,'blend neighbour:'+field,wh,amount,
                                       f'FILE {offset:#x} value={v}; range={min(bounds)}..{max(bounds)}; anchors={contributors}',scope='blend')
                for p in sorted(out.glob('*.gui')):
                    reference_roots=[]
                    for anchor in contributors:
                        refpath=audit.references.get((size_name(anchor),p.name))
                        if refpath:
                            if refpath not in audit.reference_nodes:
                                audit.reference_nodes[refpath]=nodes(refpath.read_bytes())
                            reference_roots.append(audit.reference_nodes[refpath])
                    reference=(blended_reference(reference_roots,[weight for i,weight in terms])
                               if len(reference_roots)==len(contributors) else None)
                    # process accepts a real same-size reference; blend inheritance is applied below.
                    audit.comparisons[p.name,size_name(wh)]=', '.join(
                        str(audit.references[size_name(a),p.name].relative_to(ROOT)) for a in contributors
                        if (size_name(a),p.name) in audit.references)
                    root=nodes(p.read_bytes());guis[p.name]=root
                    audit.probe(p.name,root,wh,fonts)
                    audit.stats['files']+=1;audit.stats['controls']+=sum(1 for _ in flatten(root))
                    scope='active HUD' if p.name=='mipc28x6.gui' else 'unused HUD' if p.name.startswith('mipc') or p.name in ('mi8x6.gui','maininterface.gui') else 'panel'
                    inherited=audit.reference_failures(p.name,reference,wh,fonts) if reference else None
                    audit.coverage['same-size blend references' if reference else 'unresolved blend references']+=1
                    for tag,check,amount,detail in audit.measurements(p.name,root,wh,fonts):
                        audit.emit(p.name,tag,check,wh,amount,detail,inherited,scope)
                audit.badges(wh,table,lambda name:(out/name).read_bytes(),'blend',guis)
                audit.runtime(wh,fonts,guis);audit.stats['blend sizes']+=1
                shutil.rmtree(out)
                if audit.stats['blend sizes']%100==0: print(f'ok   blend progress: {audit.stats["blend sizes"]} sizes traversed',flush=True)
            print(f'ok   blend traversal: {audit.stats["blend sizes"]} sizes, {audit.stats["rejected sizes"]} rejected',flush=True)
        else:audit.notes.append('UNTESTED blend sweep: --listed-only supplied.')
        audit.scaling_checks();audit.source_checks()
        if args.skip_build:audit.notes.append('UNTESTED Mac artifact builds: --skip-build supplied.')
        else:audit.mac_build(tmp)
        counts=audit.report()
        if geometry._DERIVED_ROOT: shutil.rmtree(geometry._DERIVED_ROOT)
    for cls in ('KMRP','inherited','by design'):
        print(f'{"FAIL" if cls=="KMRP" and counts[cls] else "ok  "} {cls}: {counts[cls]} finding groups')
    print(f'ok   coverage: {audit.stats["listed sizes"]+audit.stats["blend sizes"]} sizes, {audit.stats["files"]} files, {audit.stats["controls"]} controls')
    print(f'ok   report: {args.report}')
    return int(bool(counts['KMRP']))

if __name__=='__main__':sys.exit(main())
