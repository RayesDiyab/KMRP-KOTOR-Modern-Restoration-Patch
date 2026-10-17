"""Build an isolated, local-only GOG roster play-test from the owner's game.
Requires built KMRP modules, KPM runtime and PartyRosterLimit32K1.kpatch.
Never modifies the source game, source save, or Steam installation.
"""
from pathlib import Path
import argparse, hashlib, logging, shutil, zipfile, re, json, struct
logging.disable(logging.DEBUG)
from pykotor.common.misc import ResRef, Game
from pykotor.common.language import LocalizedString
from pykotor.extract.installation import Installation
from pykotor.resource.type import ResourceType as R
from pykotor.resource.formats.gff import read_gff, bytes_gff, GFFList
from pykotor.resource.formats.rim import read_rim
from pykotor.resource.formats.erf import ERF, ERFType, bytes_erf, read_erf
from pykotor.resource.formats.ncs import compile_nss, bytes_ncs, read_ncs
ROOT=Path(__file__).resolve().parents[2]
GOG='9C10E0450A6EECA417E036E3CDE7474FED1F0A92AAB018446D156944DEA91435'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest().upper()
def native_departure_script(original,slots):
 """Emit a balanced native-order prefix; retain the shipped script verbatim.

 The installed PyKotor compiler emits engine arguments left-to-right, contrary
 to shipped K1 NCS (e.g. AddAvailableNPCByTemplate pushes string then slot).
 Its interpreter mirrors that error, so do not use either as runtime evidence.
 """
 assert original[:9]==b'NCS V1.0B'
 prefix=bytearray();fixes=[]
 def action(number,count):prefix.extend(b'\x05\x00'+struct.pack('>HB',number,count))
 def integer(value):prefix.extend(b'\x04\x03'+struct.pack('>i',value))
 def string(value):
  raw=value.encode('ascii');prefix.extend(b'\x04\x05'+struct.pack('>H',len(raw))+raw)
 def branch(op):
  at=len(prefix);prefix.extend(bytes((op,0))+b'\0'*4);return at
 def target(at,to):struct.pack_into('>i',prefix,at+2,to-at)
 action(25,0);action(548,0);prefix.extend(b'\x0b\x22');guard=branch(0x1f)
 for slot,template in slots:
  integer(slot);action(696,1);skip=branch(0x25)
  string(f'kmrt_n{slot}');integer(slot);action(697,2)
  prefix.extend(b'\x1b\x00'+struct.pack('>i',-4))
  target(skip,len(prefix));integer(1);integer(slot);action(708,2)
 target(guard,len(prefix))
 code=bytes(prefix)+original[13:]
 return b'NCS V1.0B'+struct.pack('>I',len(code)+13)+code,len(prefix)

def prepare_exit_fixture(game,output,source_save):
 """Keep the real saved Hawk and native departure callback; inject only test NPCs."""
 target=output/'saves/000002 - EbonHawkExitTest'
 assert not target.exists(),'Refuse to replace an existing test save'
 assert (output/'Override').is_dir()
 install=Installation(game)
 slots=[(8,'p_carth'),(9,'p_cand'),(15,'p_hk47'),(16,'p_t3m4'),(31,'p_carth')]
 originals={p.name:sha(p)for p in source_save.iterdir()if p.is_file()}
 shutil.copytree(source_save,target)
 nfo=read_gff(target/'savenfo.res')
 assert nfo.root.acquire('LASTMODULE','').lower()=='ebo_m12aa','Source must be inside the Ebon Hawk'
 nfo.root.set_string('SAVEGAMENAME','ROSTER TEST - Leave Ebon Hawk')
 (target/'savenfo.res').write_bytes(bytes_gff(nfo))
 save=read_erf(target/'SAVEGAME.sav');hawk=read_erf(save.get('ebo_m12aa',R.SAV))
 git=read_gff(hawk.get('m12aa',R.GIT));triggers=GFFList();changed=0
 for trigger in git.root.get_list('TriggerList'):
  if trigger.acquire('Tag','')=='ebn12_ebonexit':
   assert str(trigger.get_resref('ScriptOnEnter'))=='k_pebn_leavhawk'
   trigger.set_resref('ScriptOnEnter',ResRef('kmrt_leave'));changed+=1
  triggers.append(trigger)
 assert changed==1,'Expected exactly one normal departure trigger'
 git.root.set_list('TriggerList',triggers);hawk.set_data('m12aa',R.GIT,bytes_gff(git))
 save.set_data('ebo_m12aa',R.SAV,bytes_erf(hawk));(target/'SAVEGAME.sav').write_bytes(bytes_erf(save))
 # UTCs must be globally available after departure as well as inside the ship.
 for slot,template in slots:
  resource=install.resource(template,R.UTC);assert resource,template
  utc=read_gff(resource.data);ref=f'kmrt_n{slot}'
  utc.root.set_resref('TemplateResRef',ResRef(ref));utc.root.set_string('Tag',ref)
  utc.root.set_locstring('FirstName',LocalizedString.from_english(f'TEST SLOT {slot}'))
  utc.root.set_locstring('LastName',LocalizedString.from_english(''))
  for key,typ,value in list(utc.root):
   if key.startswith('Script'):utc.root.set_resref(key,ResRef(''))
  path=output/'Override'/f'{ref}.utc';assert not path.exists(),path
  path.write_bytes(bytes_gff(utc))
 original_leave=read_rim(game/'modules/ebo_m12aa_s.rim').get('k_pebn_leavhawk',R.NCS)
 compiled,prefix_size=native_departure_script(original_leave,slots);read_ncs(compiled)
 assert compiled[13+prefix_size:]==original_leave[13:]
 script=output/'Override/kmrt_leave.ncs';assert not script.exists(),script
 script.write_bytes(compiled)
 (output/'fixture.nss').write_text('// Diagnostic source description only; the emitted NCS prefix uses native argument order.\n// Add missing test slots, enable selection, then fall through to the original k_pebn_leavhawk bytecode.\n')
 instructions='Launch Roster Test.cmd and load ROSTER TEST - Leave Ebon Hawk. Walk to the ship exit and leave normally. No console or warp is needed.\nThe normal departure opens party selection. Keep the original crew; extra companions are named TEST SLOT 9,15,16,31. Slot 8 is added only if originally empty. Numbers are zero-based.\nChoose 9 + 31 across pages and confirm. Check both join outside. Test with mouse and controller, Done/Back and resolution changes.\nUse this named save, not an autosave from the earlier custom module. Original saves and Steam are unchanged.\n'
 (output/'TEST-INSTRUCTIONS.txt').write_text(instructions)
 check=read_erf(read_erf(target/'SAVEGAME.sav').get('ebo_m12aa',R.SAV))
 cg=read_gff(check.get('m12aa',R.GIT))
 assert sum(str(t.acquire('ScriptOnEnter',''))=='kmrt_leave'for t in cg.root.get_list('TriggerList'))==1
 for res in save:
  if str(res.resref)!='ebo_m12aa':assert res.data==read_erf(source_save/'SAVEGAME.sav').get(str(res.resref),res.restype)
 assert {p.name:sha(p)for p in source_save.iterdir()if p.is_file()}==originals
 verification={'entry':'saved normal Ebon Hawk departure trigger','save':str(target),'save_name':'ROSTER TEST - Leave Ebon Hawk',
               'changed_trigger':'ebn12_ebonexit: k_pebn_leavhawk -> kmrt_leave -> original k_pebn_leavhawk',
               'source_save_hashes':originals,'original_roster_preserved':True,'play_tested':False,
               'files':{str(p.relative_to(output)):sha(p)for p in [target/'savenfo.res',target/'SAVEGAME.sav',script,*[(output/'Override'/f'kmrt_n{i}.utc')for i,t in slots]]}}
 (output/'exit-fixture-verification.json').write_text(json.dumps(verification,indent=2)+'\n')
 print('Normal Ebon Hawk exit fixture ready:',target,flush=True)

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--game',type=Path,required=True);p.add_argument('--save',type=Path,required=True)
 p.add_argument('--out',type=Path,default=ROOT/'build/party-roster-game')
 a=p.parse_args();g=a.game.resolve();o=a.out.resolve()
 assert not o.exists(),'Output must be a new directory'
 assert o.is_relative_to((ROOT/'build').resolve()),'Test game must stay inside ignored build/'
 assert sha(g/'swkotor.exe')==GOG,'Exact supported GOG game required'
 assert (a.save/'SAVEGAME.sav').exists(),'Supply a complete source save folder'
 original_save={x.name:sha(x)for x in a.save.iterdir()if x.is_file()}
 o.mkdir();print('Copying game resources to',o,flush=True)
 for folder in ('data','modules','rims','TexturePacks','lips','miles','movies','streammusic','streamsounds','streamwaves'):
  if (g/folder).is_dir():shutil.copytree(g/folder,o/folder)
 for name in ('swkotor.exe','chitin.key','dialog.tlk','patch.erf','Mss32.dll','Patchw32.dll'):
  shutil.copy2(g/name,o/name)
 for folder in ('Override','patches','configs','saves'):(o/folder).mkdir()
 shutil.copytree(a.save,o/'saves/000001 - RosterTest')
 shutil.copy2(g/'binkw32.dll',o/'binkw32Hooked.dll')
 for name in ('binkw32.dll','KotorPatcher.dll'):shutil.copy2(ROOT/'build/kpm-runtime'/name,o/name)
 shutil.copy2(ROOT/'build/native-runtime/kmrp-native.dll',o/'patches/kmrp.dll')
 shutil.copy2(ROOT/'build/controller-standalone/kmrp-controller.dll',o/'patches/kmrp-controller.dll')
 package=ROOT/'build/party-roster-check/roster-package/PartyRosterLimit32K1.kpatch'
 with zipfile.ZipFile(package) as z:
  (o/'patches/party-roster32.dll').write_bytes(z.read('binaries/windows_x86.dll'))
  hooks=z.read('kotor1.hooks.toml').decode();hooks=hooks[hooks.index('[[hooks]]'):].replace('[[hooks','[[patches.hooks')
 shutil.copy2(ROOT/'third_party/Kotor-Patch-Manager/lib/sqlite3.dll',o/'sqlite3.dll')
 shutil.copy2(ROOT/'third_party/Kotor-Patch-Manager/AddressDatabases/kotor1_0_3.db',o/'addresses.db')
 import sys
 sys.path.insert(0,str(ROOT/'tools'))
 import build_native_kpatch as core,build_controller_kpatch as ctrl
 # Native hooks are prepared with the exact supported clean image. The roster
 # module is loaded last; all hooks are applied before game startup resumes.
 core.verify_clean(g/'swkotor.exe')
 config='target_version_sha = "'+GOG+'"\n\n'
 for ident,dll,pieces in [('kmrp','kmrp.dll',core.config_files()),('kmrp-controller','kmrp-controller.dll',ctrl.config_files())]:
  config+='[[patches]]\nid = "'+ident+'"\ndll = "patches/'+dll+'"\n'
  config+='\n'.join(pieces.values())+'\n'
 config+='[[patches]]\nid = "party-roster-limit-32-k1"\ndll = "patches/party-roster32.dll"\n'+hooks
 (o/'patch_config.toml').write_text(config)
 for ident in ('kmrp','kmrp-controller'):
  (o/f'configs/{ident}.ini').write_text('[Patch Options]\ndebug-logs=1\n')
 shutil.copy2(ROOT/'third_party/Kotor-Patch-Manager/Patches/PartyRosterLimit32K1/Additional/partyselection.gui',o/'Override/partyselection.gui')
 (o/'swkotor.ini').write_text('[Game Options]\nEnableCheats=1\nAutoSave=0\nTutorial Popups=0\n\n[Graphics Options]\nWidth=1920\nHeight=1080\nFullScreen=0\nAllowWindowedMode=1\nV-Sync=1\nTexture Quality=2\nSoft Shadows=0\nDisable Vertex Buffer Objects=1\n\n[Sound Options]\nDisable Sound=0\n\n[Alias]\nHD0=.\\\nOVERRIDE=.\\Override\nTEMP=.\\Temp\nMODULES=.\\Modules\nLOGS=.\\Logs\nLOCALVAULT=.\\LocalVault\nDMVAULT=.\\DMVault\nSERVERVAULT=.\\ServerVault\nSTREAMMUSIC=.\\StreamMusic\nTEMPCLIENT=.\\Tempclient\nSAVES=.\\saves\nCURRENTGAME=.\\currentgame\nTEXTUREPACKS=.\\texturepacks\nSTREAMWAVES=.\\StreamWaves\n')
 prepare_exit_fixture(g,o,a.save)
 (o/'Launch Roster Test.cmd').write_text('@echo off\ncd /d "%~dp0"\nstart "" swkotor.exe\n',newline='\r\n')
 assert sha(g/'swkotor.exe')==GOG
 assert {x.name:sha(x)for x in a.save.iterdir()if x.is_file()}==original_save
 record={'source_exe_sha256':GOG,'source_save':str(a.save),'save_hashes':original_save,'slots':[8,9,15,16,31],
         'files':{str(x.relative_to(o)):sha(x)for x in [o/'swkotor.exe',o/'patches/kmrp.dll',o/'patches/kmrp-controller.dll',o/'patches/party-roster32.dll',o/'Override/partyselection.gui',o/'Override/kmrt_leave.ncs']},
         'play_tested':False,'entry':'normal Ebon Hawk exit trigger','save_name':'ROSTER TEST - Leave Ebon Hawk'}
 (o/'fixture-verification.json').write_text(json.dumps(record,indent=2)+'\n')
 print('Controlled fixture ready:',o,flush=True)
if __name__=='__main__':main()
