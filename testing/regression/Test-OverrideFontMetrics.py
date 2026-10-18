#!/usr/bin/env python3
"""Check first-load Override font timing against native bytes and real font metrics.

Compiles the production callback and supplies the owner's original font TXIs and
four current KMRP size sets. No game process, installed files or Override is changed.
"""
from pathlib import Path
import hashlib, logging, re, subprocess, sys, tomllib, zipfile
import capstone
from pykotor.resource.formats.erf import read_erf
from pykotor.resource.type import ResourceType
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import build_native_kpatch as package
from build_scaled_fonts import FONT_RESREFS, raw_txi, SCALED_FIELDS


def verify_loader(path):
    raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest().upper()
    assert sha in (package.kpatch_common.CD_1_03,package.kpatch_common.GOG),sha
    start,hook,end=0x422AF0,0x422CC1,0x422CDB
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32);md.detail=True
    ins={i.address:i for i in md.disasm(raw[start-0x400000:end-0x400000],start)}
    assert ins[hook].bytes==bytes.fromhex('8b 8c 24 14 20 00 00') and ins[hook].size==7
    assert ins[hook].mnemonic=='mov' and 'esp + 0x2014' in ins[hook].op_str
    # The register handed to the callback is still this texture through epilogue.
    assert ins[0x422B12].op_str=='edi, ecx' and ins[0x422CC8].op_str=='edi'
    assert [i.address for i in ins.values() if i.mnemonic.startswith('ret')]==[0x422CD8]
    writes_edi=[i.address for i in ins.values() if i.mnemonic=='mov' and i.operands[0].type==capstone.CS_OP_REG and i.reg_name(i.operands[0].reg)=='edi']
    assert writes_edi==[0x422B12]
    # Every reachable normal return passes the callback. Calls return normally;
    # exceptional unwinding is deliberately native. No branch enters stolen bytes.
    def reaches_return(omit):
        todo=[start];seen=set();found=False
        while todo:
            at=todo.pop()
            if at in seen or at==omit:continue
            seen.add(at);i=ins[at]
            if i.mnemonic.startswith('ret'):found=True;continue
            following=i.address+i.size
            if i.group(capstone.CS_GRP_JUMP):
                dest=i.operands[0].imm;assert dest in ins
                assert not hook<dest<hook+7
                todo.append(dest)
                if i.mnemonic!='jmp':todo.append(following)
            else:todo.append(following)
        return found
    assert reaches_return(None) and not reaches_return(hook)
    package.verify_clean(path)
    print('PASS: native loader CFG/common return, EDI ownership and all package guards:',sha[:12])


def main():
    logging.disable(logging.DEBUG)
    out=ROOT/'build/override-font-check';out.mkdir(exist_ok=True)
    verify_loader(ROOT/'build-inputs/swkotornopatch.exe')
    hooks=package.all_hooks();h=next(h for h in hooks if h.get('function')=='KmrpFontMetricsLoadedK1')
    assert h['address']==0x422CC1 and h['parameters']==[{'source':'edi','type':'pointer'}]
    assert not h.get('skip_original_bytes',False) and not h.get('exclude_from_restore')
    for file in ['src/controller-native/K1RuntimeLayout.cpp','src/controller-native/K1RuntimeResolution.cpp','src/controller-native/K1RuntimeAssets.cpp']:
        assert 'KmrpScaleOverrideFontsK1' not in (ROOT/file).read_text()
    pack=read_erf(ROOT/'build-inputs/swpc_tex_gui.erf');lines=[]
    for archive in sorted((ROOT/'build/kmrp/resources').glob('gui-*.zip')):
        size=archive.stem[4:]
        with zipfile.ZipFile(ROOT/f'build/kmrp/resources/gui-{size}.zip') as z:
            for name in FONT_RESREFS:
                original=raw_txi(pack.get(name,ResourceType.TPC))
                def field(text,key):
                    match=re.search(r'(?im)^'+re.escape(key)+r'\s+([-+0-9.eE]+)',text)
                    return float(match[1]) if match else 0.0
                member=next(n for n in z.namelist() if n.split('/')[-1]==name+'.txi')
                height=field(z.read(member).decode(),'fontheight')
                shared=field((ROOT/'assets/hd-fonts'/f'{name}.txi').read_text(),'fontheight')
                lines.append(' '.join([name,str(height),*[str(field(original,key))for key in SCALED_FIELDS],size.split('x')[1],str(shared)]))
    fixture=out/'metrics.txt';fixture.write_text('\n'.join(lines)+'\n')
    vc=re.search(r'^set VC=(.+)$',(ROOT/'src/controller-native/build_native_runtime.cmd').read_text(),re.M)[1].strip()
    exe=out/'override-font-metrics.exe'
    args=['cl','/nologo','/O2','/Gy','/std:c++17','/EHsc','/W3','/I'+str(ROOT/'build/native-runtime'),'/I'+str(ROOT/'src/controller-native'),str(ROOT/'testing/regression/override_font_metrics_harness.cpp'),'/Fo'+str(out/'harness.obj'),'/Fe'+str(exe),'/link','/OPT:REF','user32.lib','bcrypt.lib','crypt32.lib']
    cmd=out/'build.cmd';cmd.write_text('@echo off\ncall "'+vc+'" x86 >nul\nif errorlevel 1 exit /b %errorlevel%\n'+subprocess.list2cmdline(args)+'\nexit /b %errorlevel%\n',newline='\r\n')
    subprocess.run(['cmd','/d','/c',str(cmd)],cwd=ROOT,check=True)
    subprocess.run([str(exe),str(fixture)],check=True)


if __name__=='__main__':main()
