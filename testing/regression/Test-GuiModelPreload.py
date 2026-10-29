"""Exercise preview preload priority and hidden-render state restoration."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    out = ROOT / 'build/gui-model-preload-check'
    out.mkdir(parents=True, exist_ok=True)
    production = (ROOT / 'src/controller-native/K1GuiModelPreload.h').read_text(encoding='utf-8')
    production = production.replace('#pragma once', '').replace('0x0078D1E4', 'reinterpret_cast<std::uintptr_t>(&do3d)')
    production = production.replace('0x0078E574', 'reinterpret_cast<std::uintptr_t>(&::frameTime)')
    harness = r'''
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <stdexcept>
static int do3d=1, target=0x405, calls=0;
static float frameTime=0.125f;
static bool context=true, failDraw=false;
static std::vector<float> deltas;
static unsigned char panel[0x1600]{}, scenes[6][0xF8]{};
static std::vector<std::string> messages;
void ControllerLogK1(const char* s){messages.emplace_back(s);}
static void Require(bool ok,const char* s){if(!ok){std::puts(s);std::exit(1);}}
static void* WINAPI Context(){return context?reinterpret_cast<void*>(1):nullptr;}
static void WINAPI Get(unsigned name,int* out){Require(name==0xC01,"Unexpected GL query");*out=target;}
static void WINAPI Buffer(unsigned value){target=value;}
static void __fastcall NativeView(void* view,void*,float dt){
 ++calls;deltas.push_back(dt);
 auto* scene=*reinterpret_cast<unsigned char**>(static_cast<unsigned char*>(view)+0x70);
 if(target==0){Require(dt==0.0f&&frameTime==0.0f,"Warm draw advanced animation");Require(*reinterpret_cast<int*>(scene+0xD4)==0,"Warm draw allowed visible postprocessing");}
 else Require(target==0x405&&*reinterpret_cast<int*>(scene+0xD4)==1&&frameTime==0.125f,"Visible draw state was not restored");
 if(failDraw)throw std::runtime_error("fixture");
 ++*reinterpret_cast<int*>(scene+0x50);
}
// PRODUCTION
static void SetUp(unsigned vt,int count){
 std::memset(panel,0,sizeof panel);std::memset(scenes,0,sizeof scenes);
 *reinterpret_cast<unsigned*>(panel)=vt;
 const int first=count==6?0x230:0x360;
 for(int i=0;i<count;++i){auto* view=panel+first+i*0x25C;
  *reinterpret_cast<unsigned*>(view)=0x752E30;
  *reinterpret_cast<unsigned*>(view+0x44)=2;
  *reinterpret_cast<void**>(view+0x70)=scenes[i];
  *reinterpret_cast<int*>(scenes[i]+0x58)=5;
  *reinterpret_cast<int*>(scenes[i]+0xD4)=1;
 }
}
int main(){
 K1GuiModelPreload::resolved=true;
 K1GuiModelPreload::graphics={&Context,&Get,&Buffer};
 const auto draw=reinterpret_cast<K1GuiModelPreload::Draw>(&NativeView);
 SetUp(0x758020,6);K1GuiModelPreload::Queue(panel);
 Require(K1GuiModelPreload::Pending()&&calls==0,"Queued model work rendered before a graphics draw");
 for(int i=0;i<6;++i){void* view=panel+0x230+i*0x25C;
  Require(K1GuiModelPreload::Prime(view,draw),"First preview was not primed");
  Require(target==0x405,"Draw buffer leaked out of warm pass");
  draw(view,0.125f);
  Require(*reinterpret_cast<int*>(scenes[i]+0x50)==2,"First visible frame did not follow hidden initialization");
  Require(!K1GuiModelPreload::Prime(view,draw),"Preview primed twice");
 }
 Require(calls==12&&!K1GuiModelPreload::Pending(),"Model priority queue did not drain");
 Require(messages.empty(),"Priming performed immediate trace-file writes");
 K1GuiModelPreload::Forget(panel);Require(K1GuiModelPreload::ready.empty(),"Destroyed panel kept stale preload state");
 SetUp(0x752F70,1);K1GuiModelPreload::Queue(panel);void* view=panel+0x360;
 context=false;Require(!K1GuiModelPreload::Prime(view,draw)&&K1GuiModelPreload::Pending(),"Missing GL context was not deferred");
 context=true;Require(K1GuiModelPreload::Prime(view,draw),"Main menu model did not prime");draw(view,0.125f);
 K1GuiModelPreload::Forget(panel);SetUp(0x752F70,1);K1GuiModelPreload::Queue(panel);
 do3d=0;Require(!K1GuiModelPreload::Pending(),"Disabled 3D blocked lower-priority GUI work");do3d=1;
 *reinterpret_cast<unsigned*>(static_cast<unsigned char*>(view)+0x44)=0;
 K1GuiModelPreload::Queue(panel);Require(!K1GuiModelPreload::Pending(),"Hidden view blocked optional GUI uploads");
 *reinterpret_cast<unsigned*>(static_cast<unsigned char*>(view)+0x44)=2;
 K1GuiModelPreload::Queue(panel);failDraw=true;
 try{K1GuiModelPreload::Prime(view,draw);Require(false,"Fixture did not throw");}catch(const std::runtime_error&){}
 Require(target==0x405&&*reinterpret_cast<int*>(scenes[0]+0xD4)==1&&frameTime==0.125f,"Exception leaked graphics state");
 failDraw=false;K1GuiModelPreload::Forget(panel);
 std::puts("PASS: six class previews and main menu prime before visible draw; zero animation delta; color output and effects restored; no repeat, stale job or immediate log write; missing context deferred");
}
'''
    cpp = out / 'gui-model-preload.cpp'
    cpp.write_text(harness.replace('// PRODUCTION', production), encoding='utf-8')
    build = (ROOT / 'src/controller-native/build_controller_standalone.cmd').read_text(encoding='utf-8')
    vc = re.search(r'^set VC=(.+)$', build, re.M).group(1).strip()
    exe = out / 'gui-model-preload.exe'
    args = ['cl', '/nologo', '/O2', '/std:c++17', '/EHsc', '/Isrc/controller-native', str(cpp),
            '/Fo' + str(out) + '/', '/Fe' + str(exe)]
    cmd = out / 'build.cmd'
    cmd.write_text('@echo off\ncall "' + vc + '" x86 >nul\nif errorlevel 1 exit /b %errorlevel%\n'
                   + subprocess.list2cmdline(args) + '\nif errorlevel 1 exit /b %errorlevel%\n'
                   + subprocess.list2cmdline([str(exe)]) + '\n', encoding='utf-8')
    return subprocess.run(['cmd', '/d', '/c', str(cmd)], cwd=ROOT).returncode


if __name__ == '__main__':
    raise SystemExit(main())
