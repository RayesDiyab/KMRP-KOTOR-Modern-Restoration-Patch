#!/usr/bin/env python3
"""Inventory GUI text definitions, including absent FONT fields; candidate groups are review aids, never runtime rules.

Reads generated archives only. Writes metadata, not game text or resources.
See docs/text-layout-inventory.md for evidence boundaries and proposed policies.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import zipfile
from pykotor.resource.formats.gff import GFFList, GFFStruct, read_gff

ROOT = Path(__file__).resolve().parents[1]


def rect(node):
    e = node.acquire('EXTENT', None)
    return [int(e.acquire(k, 0)) for k in ('LEFT', 'TOP', 'WIDTH', 'HEIGHT')] if isinstance(e, GFFStruct) else None


def group(font):
    # Same resource-family split as K1TextOptionsPolicy.h, not a screen-use claim.
    font = font.lower()
    if font.startswith(('fnt_d', 'fnt_credits')): return 'subtitles-body'
    if font.startswith('dialogfont10x10'): return 'small'
    if font == 'fnt_console': return 'hud-console'
    return 'menus-replies' if font else 'unknown'


def candidate(file, tag, kind, prototype, family):
    if prototype: return 'list-row-template', 'Inside PROTOITEM; native row class and scroll behavior need review'
    if file.startswith(('maininterface.', 'mi8x6.', 'mipc')):
        return 'hud-slot', 'HUD resource; may be empty artwork slot or runtime text; active variant unverified'
    if 'TITLE' in tag.upper(): return 'fixed-caption', 'Title-like tag; intended line count needs review'
    if kind in (6, 7): return 'control-caption', 'Button/toggle-like template; native class and text rectangle need review'
    if family == 'subtitles-body': return 'body-text', 'Body font family; wrapping and scrolling must be verified'
    return 'unclassified-slot', 'No behavior established from template metadata'


def slots(root, file):
    def walk(node, path, prototype='', owner_tag=''):
        tag = str(node.acquire('TAG', ''))
        kind = int(node.acquire('CONTROLTYPE', -1))
        text = node.acquire('TEXT', None)
        if isinstance(text, GFFStruct):
            font = str(text.acquire('FONT', '')).lower()
            family = group(font)
            literal = bool(text.acquire('TEXT', ''))
            ref = int(text.acquire('STRREF', -1))
            valid_ref = ref not in (-1, 0xFFFFFFFF)
            border = node.acquire('BORDER', None)
            c, reason = candidate(file, tag, kind, prototype, family)
            yield {'gui': file, 'path': path + '/TEXT', 'tag': tag, 'control_type': kind,
                   'prototype_owner': prototype, 'owner_tag': owner_tag,
                   'font': font, 'font_source':'explicit' if text.exists('FONT') else 'native-default-or-inherited', 'font_group': family,
                   'alignment': int(text.acquire('ALIGNMENT', -1)), 'extent': rect(node),
                   'border_dimension': int(border.acquire('DIMENSION', 0)) if isinstance(border, GFFStruct) else 0,
                   'border_inner_offset': int(border.acquire('INNEROFFSET', 0)) if isinstance(border, GFFStruct) else 0,
                   'list_padding': int(node.acquire('PADDING', 0)),
                   'has_scrollbar_template': isinstance(node.acquire('SCROLLBAR', None), GFFStruct),
                   'content_source': 'literal-and-talktable' if literal and valid_ref else 'literal' if literal else 'talktable' if valid_ref else 'empty-or-runtime',
                   'candidate_group': c, 'candidate_reason': reason,
                   'behavior_status': 'unreviewed', 'native_class': 'unverified',
                   'actual_text_rectangle': 'unverified', 'intended_line_count': 'unverified',
                   'runtime_test': 'not-tested', 'proposed_policy': 'review-before-assignment'}
        for label, _, value in node:
            if isinstance(value, GFFStruct):
                yield from walk(value, path + '/' + label,
                                (path if label == 'PROTOITEM' else prototype),
                                tag if label == 'PROTOITEM' else owner_tag)
            elif isinstance(value, GFFList):
                for i, child in enumerate(value):
                    label_tag = str(child.acquire('TAG', ''))
                    yield from walk(child, path + '/' + label + '[' + str(i) + ']:' + label_tag, prototype, owner_tag)
    yield from walk(root, 'root')


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--resources', type=Path, default=ROOT / 'build/kmrp/resources')
    p.add_argument('--baseline', default='1920x1080')
    p.add_argument('--all', action='store_true', help='Compare every listed resolution archive')
    p.add_argument('--out', type=Path, default=ROOT / 'build/text-layout-inventory')
    args = p.parse_args()
    packs = sorted(args.resources.glob('gui-*.zip')) if args.all else [args.resources / ('gui-' + args.baseline + '.zip')]
    baseline = args.resources / ('gui-' + args.baseline + '.zip')
    if baseline not in packs: raise ValueError('Baseline archive must be present')
    observations, identities = {}, []
    instances = 0
    for pack in packs:
        resolution = pack.stem.removeprefix('gui-')
        gui_count = count = 0
        with zipfile.ZipFile(pack) as z:
            for name in sorted(z.namelist()):
                if not name.lower().endswith('.gui'): continue
                gui_count += 1
                for row in slots(read_gff(z.read(name)).root, name):
                    key = (row['gui'], row['path'])
                    by_size = observations.setdefault(key, {})
                    if resolution in by_size: raise ValueError('Duplicate text slot: ' + str(key))
                    by_size[resolution] = row
                    count += 1
        instances += count
        identities.append({'name': pack.name, 'sha256': hashlib.sha256(pack.read_bytes()).hexdigest(),
                           'bytes': pack.stat().st_size, 'gui_files': gui_count, 'text_slots': count})
    rows = []
    for key, sizes in sorted(observations.items()):
        selected = sizes.get(args.baseline)
        row = dict(selected or next(iter(sizes.values())))
        extent = row.pop('extent')
        row['measurement_resolution'] = args.baseline if selected else next(iter(sizes))
        for i, name in enumerate(('left', 'top', 'width', 'height')): row[name] = extent[i] if extent else ''
        extents = [r['extent'] for r in sizes.values() if r['extent']]
        row['sizes_present'] = len(sizes)
        row['sizes_expected'] = len(packs)
        row['template_height_min'] = min((e[3] for e in extents), default='')
        row['template_height_max'] = max((e[3] for e in extents), default='')
        row['font_variants'] = ';'.join(sorted({r['font'] for r in sizes.values()}))
        row['alignment_variants'] = ';'.join(map(str, sorted({r['alignment'] for r in sizes.values()})))
        # Do not silently reconcile conflicting source definitions.
        row['definition_review'] = 'needed' if len({(r['control_type'], r['font_group'], r['alignment'], r['candidate_group']) for r in sizes.values()}) > 1 or len(sizes) != len(packs) else 'consistent-in-inspected-packs'
        rows.append(row)
    args.out.mkdir(parents=True, exist_ok=True)
    if not rows: raise ValueError('No font-bearing text definitions found')
    write_csv(args.out / 'controls.csv', rows)
    summary = {'baseline': args.baseline, 'archives': len(packs), 'gui_instances': sum(r['gui_files'] for r in identities),
               'text_slot_instances': instances, 'distinct_slots': len(rows),
               'distinct_gui_files': len({r['gui'] for r in rows}),
               'candidate_groups': dict(sorted(Counter(r['candidate_group'] for r in rows).items())),
               'content_sources': dict(sorted(Counter(r['content_source'] for r in rows).items())),
               'font_sources': dict(sorted(Counter(r['font_source'] for r in rows).items())),
               'definition_reviews': dict(Counter(r['definition_review'] for r in rows)),
               'provenance': identities,
               'limits': ['Template extents are not native text-content rectangles.',
                          'All behavioral groups are candidates requiring review; no runtime policy is assigned.',
                          'Empty slots may become text at runtime; none are discarded.',
                          'Inactive HUD variants are included, without claiming simultaneous visibility.',
                          'Dynamically constructed controls and third-party GUIs require additional inventory.',
                          'No maximum font size is inferred from a template rectangle.'],
               'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (args.out / 'manifest.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k not in ('provenance', 'limits')}, indent=2))


if __name__ == '__main__': main()
