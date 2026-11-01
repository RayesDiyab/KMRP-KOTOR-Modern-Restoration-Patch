#!/usr/bin/env python3
"""Compile the real roster adapter; inspect its GFF output at every built size.
Needs the normal build inputs / GUI archives, the KPM submodule and MSVC x86.
No game process is started and the player's files are never changed.
"""
from pathlib import Path
import copy
import logging
import re
import subprocess
import zipfile
from pykotor.resource.formats.gff import read_gff, bytes_gff, GFFList
from pykotor.common.misc import ResRef

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/party-roster-check'

def controls(gui):
    return {c.acquire('TAG',''): c for c in gui.root.get_list('CONTROLS')}

def extent(c):
    e = c.get_struct('EXTENT')
    return tuple(e.acquire(k,0) for k in ('LEFT','TOP','WIDTH','HEIGHT'))

def functional(c):
    # These data bind the engine's native callbacks and roster/page behaviour.
    result = {}
    for key in ('CONTROLTYPE','ID','TAG','Obj_Parent','Obj_ParentID','Obj_Locked','ISSELECTED'):
        if c.exists(key): result[key] = c.acquire(key,None)
    if c.exists('MOVETO'): result['MOVETO'] = {n:v for n,t,v in c.get_struct('MOVETO')}
    if c.exists('TEXT'):
        result['TEXT'] = {n:str(v) for n,t,v in c.get_struct('TEXT') if n in ('TEXT','STRREF')}
    return result

def main():
    logging.disable(logging.DEBUG)
    OUT.mkdir(parents=True,exist_ok=True)
    build = (ROOT/'src/controller-native/build_native_runtime.cmd').read_text()
    vc = re.search(r'^set VC=(.+)$',build,re.MULTILINE).group(1).strip()
    exe = OUT/'party-roster-gui.exe'
    args=['cl','/nologo','/O2','/std:c++17','/EHsc','/W4','/I'+str(ROOT/'src/controller-native'),
          str(ROOT/'src/controller-native/K1PartyRosterGui.cpp'),str(ROOT/'testing/regression/party_roster_gui_harness.cpp'),
          '/Fo'+str(OUT)+'\\','/Fe'+str(exe)]
    cmd=OUT/'build.cmd'
    cmd.write_text('@echo off\ncall "'+vc+'" x86 >nul\nif errorlevel 1 exit /b %errorlevel%\n'+subprocess.list2cmdline(args)+'\nexit /b %errorlevel%\n',newline='\r\n')
    subprocess.run(['cmd.exe','/d','/c',str(cmd)],cwd=ROOT,check=True)
    source=ROOT/'third_party/Kotor-Patch-Manager/Patches/PartyRosterLimit32K1/Additional/partyselection.gui'
    original=source.read_bytes();roster=read_gff(original);rc=controls(roster)
    stock=controls(read_gff(ROOT/'build-inputs/vanilla-gui/partyselection.gui'))
    for prefix in ('BTN_NPC','LBL_CHAR','LBL_NA'):
        for i in range(9):assert extent(stock[f'{prefix}{i}'])==(54+91*(i%3),109+88*(i//3),85,85)
    assert extent(stock['BTN_ACCEPT'])==(73,372,235,33)
    assert extent(stock['BTN_DONE'])==(247,410,146,28)

    # Distinct portrait/text and navigation content must survive styling.
    changed=GFFList()
    for c in roster.root.get_list('CONTROLS'):
        c=copy.deepcopy(c);tag=c.acquire('TAG','')
        if tag=='LBL_CHAR31':
            border=c.get_struct('BORDER');border.set_resref('FILL',ResRef('kmr_test31'));c.set_struct('BORDER',border)
        if tag=='BTN_PAGE_NEXT':
            text=c.get_struct('TEXT');text.set_string('TEXT','NEXT FIXTURE');c.set_struct('TEXT',text)
        changed.append(c)
    roster.root.set_list('CONTROLS',changed);rc=controls(roster)
    fixture=OUT/'roster.gui';fixture.write_bytes(bytes_gff(roster))
    samples=sorted((ROOT/'build/kmrp/resources').glob('gui-*.zip'))
    assert len(samples)>=66,'Run the normal resource build first'
    inputs=[]
    for archive in samples:
        with zipfile.ZipFile(archive) as z:
            name=next(n for n in z.namelist() if n.split('/')[-1]=='partyselection.gui')
            inputs.append((archive.stem,z.read(name)))
    # Exercise the production blend helper too: sizes absent from the bank.
    helper=ROOT/'build/native-runtime/bank-helper/kmrp-guiblend.exe'
    for w,h in ((1800,1169),(2056,1329),(1710,1112),(1920,1243),(3440,1400)):
        nearest=min(samples,key=lambda p:(abs(int(p.stem.split('-')[1].split('x')[1])-h),abs(int(p.stem.split('-')[1].split('x')[0])/int(p.stem.split('-')[1].split('x')[1])-w/h)))
        folder=OUT/f'blend-{w}x{h}';folder.mkdir(exist_ok=True)
        with zipfile.ZipFile(nearest) as z:
            for name in z.namelist():
                if name.endswith('.txi') or name.endswith('kmrp_prompts.txt'):
                    (folder/Path(name).name).write_bytes(z.read(name))
        subprocess.run([str(helper),str(ROOT/'build/kmrp/gui-blend.bin'),str(w),str(h),str(folder),str(folder)],check=True,capture_output=True)
        inputs.append((f'blend-{w}x{h}',(folder/'partyselection.gui').read_bytes()))
    cases=0
    for name,data in inputs:
        target=OUT/'target.gui';target.write_bytes(data)
        dest=OUT/(name+'.gui')
        subprocess.run([str(exe),str(fixture),str(target),str(dest)],check=True)
        result=read_gff(dest);out=controls(result);kmrp=controls(read_gff(data))
        assert out.keys()==rc.keys()
        assert extent(result.root)==extent(read_gff(data).root)
        for tag,c in rc.items():
            assert functional(out[tag])==functional(c),(name,tag,'functional fields')
        for page in range(2):
            boxes=[extent(out['BTN_NPC'+str(page*16+i)]) for i in range(16)]
            boxes += [extent(out[t]) for t in ('BTN_ACCEPT','BTN_DONE','BTN_BACK','BTN_PAGE_PREV','BTN_PAGE_NEXT')]
            for i,a in enumerate(boxes):
                assert a[2]>0 and a[3]>0
                root=extent(result.root)
                assert 0<=a[0] and 0<=a[1] and a[0]+a[2]<=root[2] and a[1]+a[3]<=root[3],(name,a,root)
                for b in boxes[i+1:]:
                    assert a[0]+a[2]<=b[0] or b[0]+b[2]<=a[0] or a[1]+a[3]<=b[1] or b[1]+b[3]<=a[1],(name,'overlap')
        for tag in ('BTN_DONE','BTN_BACK','BTN_ACCEPT'):
            assert extent(out[tag])==extent(kmrp[tag])
        assert str(out['LBL_CHAR31'].get_struct('BORDER').get_resref('FILL'))=='kmr_test31'
        for tag in ('BTN_PAGE_PREV','BTN_PAGE_NEXT'):
            assert extent(out[tag])[2] == extent(out[tag])[3],(name,tag,'square arrow hit target')
            assert out[tag].get_struct('TEXT').get_resref('FONT')==kmrp['BTN_DONE'].get_struct('TEXT').get_resref('FONT')
            assert out[tag].get_struct('BORDER').get_resref('FILL')==rc[tag].get_struct('BORDER').get_resref('FILL')
        generated=OUT/(name+'-generated.gui')
        subprocess.run([str(exe),'--generate',str(target),str(generated)],check=True)
        created=controls(read_gff(generated));official=controls(read_gff(original))
        assert created.keys()==official.keys(),(name,'generated tag contract')
        for tag in official:
            assert functional(created[tag])==functional(official[tag]),(name,tag,'generated functional contract')
        for tag in out:
            assert extent(created[tag])==extent(out[tag]),(name,tag,'generated/supplied geometry')
        cases+=1
    # Unsupported/invalid data must fail before replacing an existing output.
    bad=OUT/'bad.gui';dest=OUT/'keep.gui';dest.write_bytes(b'keep this file')
    for data in [b'',original[:100],b'not a GUI',original[:56]]:
        bad.write_bytes(data)
        result=subprocess.run([str(exe),str(bad),str(target),str(dest)],capture_output=True)
        assert result.returncode==1 and dest.read_bytes()==b'keep this file'
    duplicate=copy.deepcopy(roster);dc=controls(duplicate);changed=GFFList()
    for c in duplicate.root.get_list('CONTROLS'):
        c=copy.deepcopy(c)
        if c.acquire('TAG','')=='BTN_NPC31':c.set_int32('ID',dc['BTN_NPC0'].get_int32('ID'))
        changed.append(c)
    duplicate.root.set_list('CONTROLS',changed)
    bad.write_bytes(bytes_gff(duplicate))
    assert subprocess.run([str(exe),str(bad),str(target),str(dest)],capture_output=True).returncode==1
    assert source.read_bytes()==original
    # Compile the actual cache/Override integration, replacing only external
    # game helpers and the process image with controlled fixture data.
    runtime=OUT/'party-roster-runtime.exe'
    args=['cl','/nologo','/O2','/std:c++17','/EHsc','/W3','/I'+str(ROOT/'build/native-runtime'),
          '/I'+str(ROOT/'src/controller-native'),str(ROOT/'testing/regression/party_roster_runtime_harness.cpp'),
          str(ROOT/'src/controller-native/K1PartyRosterGui.cpp'),'/Fo'+str(OUT)+'\\','/Fe'+str(runtime),
          '/link','user32.lib','bcrypt.lib','crypt32.lib']
    cmd.write_text('@echo off\ncall "'+vc+'" x86 >nul\nif errorlevel 1 exit /b %errorlevel%\n'+subprocess.list2cmdline(args)+'\nexit /b %errorlevel%\n',newline='\r\n')
    subprocess.run(['cmd.exe','/d','/c',str(cmd)],cwd=ROOT,check=True)
    for size in ('1920x1080','2560x1440'):
        with zipfile.ZipFile(ROOT/f'build/kmrp/resources/gui-{size}.zip') as z:
            n=next(n for n in z.namelist() if n.split('/')[-1]=='partyselection.gui')
            (OUT/f'base-{size}.gui').write_bytes(z.read(n))
    subprocess.run([str(runtime),str(fixture),str(OUT/'base-1920x1080.gui'),str(OUT/'base-2560x1440.gui')],check=True)
    controller=OUT/'party-roster-controller.exe'
    args=['cl','/nologo','/O2','/Gy','/std:c++17','/EHsc','/W3',
          str(ROOT/'testing/regression/party_roster_controller_harness.cpp'),
          '/Fo'+str(OUT/'controller.obj'),'/Fe'+str(controller),'/link','/OPT:REF','user32.lib']
    cmd.write_text('@echo off\ncall "'+vc+'" x86 >nul\nif errorlevel 1 exit /b %errorlevel%\n'+subprocess.list2cmdline(args)+'\nexit /b %errorlevel%\n',newline='\r\n')
    subprocess.run(['cmd.exe','/d','/c',str(cmd)],cwd=ROOT,check=True)
    subprocess.run([str(controller)],check=True)
    print(f'PASS: {cases} resolutions; generated and supplied layouts; all roster IDs/captions/navigation retained; both 16-slot pages non-overlapping; portraits/page fills retained; malformed/duplicate-ID inputs fail safely.')

if __name__=='__main__': main()
