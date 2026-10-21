#!/usr/bin/env python3
"""Native UI lifecycle + shared font source checks. Does not launch/install KOTOR."""
from pathlib import Path
import re
import subprocess
import sys
import zipfile
from PIL import Image
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
    original=ROOT/'build/native-runtime/original-fonts'
    # HD Original keeps the original's layout at six times its size: as many glyphs,
    # the cell height and baseline, and every ASCII letter's step, its cell's width and
    # the spacing after it (letter gaps, word spaces, line lengths and the HUD's even
    # cells), tools/build_hd_original_fonts.py. The step, not the cell alone: the HUD
    # font's cells are an outline wider and its spacing that much less (2026-10-21).
    def metrics(txi):
        lines=[l.split() for l in txi.splitlines() if l.strip()]
        head={l[0]:float(l[1]) for l in lines if len(l)==2 and l[0] in ('numchars','fontheight','baselineheight','texturewidth','spacingR')}
        upper=next(i for i,l in enumerate(lines) if l[0]=='upperleftcoords')
        lower=next(i for i,l in enumerate(lines) if l[0]=='lowerrightcoords')
        n=int(head['numchars'])
        widths=[round((float(lines[lower+1+c][0])-float(lines[upper+1+c][0]))*head['texturewidth']*100
                      +head.get('spacingR',0)*100) for c in range(n)]
        return head,widths
    for i,name in enumerate(FONT_RESREFS):
        head,widths=metrics((original/f'kmrfog{i:02d}.txi').read_text())
        hd,hdw=metrics(bank.hd_original(name,'.txi').read_text())
        assert hd['numchars']==head['numchars'],name
        for key in ('fontheight','baselineheight'):
            assert abs(hd[key]-head[key]*6)<0.011,(name,key,hd[key],head[key])
        wrong=[chr(c) for c in range(0x20,0x7F) if hdw[c]!=widths[c]*6]
        assert not wrong,(name,''.join(wrong))
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
    print('PASS: all 1,188 previous default font heights retained; all 18 HD Original fonts keep the original\'s glyphs, '
          'cell height, baseline and ASCII letter steps at six times the size.')
    print('PASS: all 18 Original Font atlases preserve the game artwork pixel for pixel, at its original dimensions.')


if __name__=='__main__':main()
