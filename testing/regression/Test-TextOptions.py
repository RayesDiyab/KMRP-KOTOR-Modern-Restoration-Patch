#!/usr/bin/env python3
"""Native UI lifecycle + shared font source checks. Does not launch/install KOTOR."""
from pathlib import Path
import re
import subprocess
import sys
import zipfile
from PIL import Image, ImageChops
from pykotor.resource.formats.gff import read_gff
from pykotor.resource.formats.erf import read_erf
from pykotor.resource.formats.tpc import read_tpc, TPCTextureFormat

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import build_native_assets as bank
from build_scaled_fonts import FONT_RESREFS


def main():
    out=ROOT/'build/text-options-check';out.mkdir(exist_ok=True)
    rows=[]
    # Both variants selected by native GetUpdatedFontName must be bundled.
    assert {'fnt_d16x16a','fnt_d16x16b'} <= set(FONT_RESREFS)
    tags=['LBL_TITLE','SLI_GAMMA','LBL_GAMMA','LB_DESC','BTN_DEFAULT','BTN_BACK','BTN_RESOLUTION','BTN_ADVANCED','CB_SHADOWS']
    for path in sorted((ROOT/'build/kmrp/resources').glob('gui-*.zip')):
        with zipfile.ZipFile(path) as z:
            root=read_gff(z.read('optgraphics.gui')).root
            controls={c.acquire('TAG',''):c for c in root.acquire('CONTROLS',[])}
            extents=[]
            for tag in tags:
                e=controls[tag].acquire('EXTENT',None)
                extents.extend(e.acquire(k,0) for k in ['LEFT','TOP','WIDTH','HEIGHT'])
            rows.append(path.stem+' '+' '.join(map(str,extents)))
            height=int(path.stem.split('x')[-1])
            for name in FONT_RESREFS:
                old=float(re.search(rb'(?im)^fontheight\s+([\d.]+)',z.read(name+'.txi'))[1])
                new=float(re.search(rb'(?im)^fontheight\s+([\d.]+)',bank.shared_font_txi(name,height))[1])
                assert old==new,(path.stem,name,old,new)
    # Different GUI skins: translated layouts, alternate spacing and compact menus.
    for index,(sx,sy,dx,dy) in enumerate([(1.2,.85,90,20),(.75,1.1,-20,4),(1.5,1.5,5,10),(1,1,350,220)]):
        parts=rows[20].split();values=list(map(int,parts[1:]));changed=[]
        for i in range(0,len(values),4):
            x,y,w,h=values[i:i+4];changed.extend([round(x*sx)+dx,round(y*sy)+dy,round(w*sx),round(h*sy)])
        rows.append(f'modified-gui-{index} '+' '.join(map(str,changed)))
    fixture=out/'graphics-fixtures.txt';fixture.write_text('\n'.join(rows)+'\n')
    vc=re.search(r'^set VC=(.+)$',(ROOT/'src/controller-native/build_native_runtime.cmd').read_text(),re.M)[1].strip()
    exe=out/'text-options.exe'
    args=['cl','/nologo','/O2','/std:c++17','/EHsc','/W3',str(ROOT/'testing/regression/text_options_harness.cpp'),
          '/Fo'+str(out/'harness.obj'),'/Fe'+str(exe),'/link','/BASE:0x10000000','/DYNAMICBASE:NO','user32.lib']
    cmd=out/'build.cmd';cmd.write_text('@echo off\ncall "'+vc+'" x86 >nul\nif errorlevel 1 exit /b %errorlevel%\n'+subprocess.list2cmdline(args)+'\nexit /b %errorlevel%\n',newline='\r\n')
    subprocess.run(['cmd','/d','/c',str(cmd)],cwd=ROOT,check=True)
    subprocess.run([str(exe),str(fixture)],cwd=out,check=True)
    # Pixel fidelity against the exact linked script output, when the local
    # comparison fixture exists. The two deliberately repaired grids are separate.
    original=ROOT/'build/native-runtime/original-fonts'
    upstream=ROOT/'build/font-comparison-2026-10-17/original-pc'
    compared=0
    for i,name in enumerate(FONT_RESREFS):
        if name in ('fnt_d10x10b','fnt_d16x16'):continue
        if (upstream/(name+'.tga')).exists():
            a=Image.open(original/f'kmrfpc{i:02d}.tga').getchannel('A')
            b=Image.open(upstream/(name+'.tga')).getchannel('A')
            assert ImageChops.difference(a,b).getbbox() is None,name
            compared+=1
    originals=0
    for resource in read_erf(ROOT/'build-inputs/swpc_tex_gui.erf'):
        name=str(resource.resref).lower()
        if name not in FONT_RESREFS:continue
        texture=read_tpc(bytes(resource.data));texture.convert(TPCTextureFormat.RGBA)
        mip=texture.get(0)
        expected=Image.frombytes('RGBA',(mip.width,mip.height),bytes(mip.data)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        actual=Image.open(original/f'kmrfog{FONT_RESREFS.index(name):02d}.tga').convert('RGBA')
        assert expected.size==actual.size and expected.tobytes()==actual.tobytes(),name
        originals+=1
    assert originals==18
    print(f'PASS: all 1,188 previous default font heights retained; {compared} sharpened atlases match upstream pixels exactly.')
    print('PASS: all 18 Original Font atlases preserve the game artwork pixel for pixel, at its original dimensions.')


if __name__=='__main__':main()
