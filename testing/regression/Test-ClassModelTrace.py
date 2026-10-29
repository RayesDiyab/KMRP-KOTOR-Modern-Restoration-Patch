"""Verify level 2 class-model tracing delegates Draw and only reads texture state."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    out = ROOT / 'build/class-model-trace-check'
    out.mkdir(parents=True, exist_ok=True)
    production = (ROOT / 'src/controller-native/K1ClassModelTrace.h').read_text(encoding='utf-8')
    production = production.replace('#pragma once', '').replace('constexpr std::uintptr_t', 'const std::uintptr_t')
    for address, target in {'0x006DC030': '&NativeDraw', '0x00758054': '&drawSlot',
                            '0x0067ACB0': '&NativeViewDraw', '0x00752E68': '&viewDrawSlot',
                            '0x007A4774': '&pending', '0x007A4714': '&locked',
                            '0x007A4798': '&textureList', '0x007A479C': '&total'}.items():
        production = production.replace(address, 'reinterpret_cast<std::uintptr_t>(' + target + ')')
    harness = r'''
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
static int level=2, calls=0, pending=0, total=1;
static unsigned locked=0;
static float seenDelta=0;
static unsigned char texture[0xE8]{};
static void* items[]={texture};
static void** textureList=items;
static std::vector<std::string> messages;
static unsigned char panelData[0x1600]{}, sceneData[6][0xF8]{}, managers[6][0x20]{}, lights[6][0x58]{};
static void* lightLists[6][1]{};
static int viewCalls=0;
int KmrpDebugLevel(){return level;}
void ControllerLogK1(const char* text){messages.emplace_back(text);}
void __fastcall NativeViewDraw(void* view, void*, float){
 ++viewCalls;
 auto* scene=*reinterpret_cast<unsigned char**>(static_cast<unsigned char*>(view)+0x70);
 ++*reinterpret_cast<int*>(scene+0x50);
 auto* manager=*reinterpret_cast<unsigned char**>(scene+0x80);
 *reinterpret_cast<int*>(manager+0x0C)=1;
}
static void* viewDrawSlot=reinterpret_cast<void*>(&NativeViewDraw);
void __fastcall NativeDraw(void* panel, void*, float dt){
 ++calls;seenDelta=dt;pending=3;
 for(int i=0;i<6;++i) reinterpret_cast<void(__thiscall*)(void*,float)>(viewDrawSlot)(static_cast<unsigned char*>(panel)+0x230+i*0x25C,dt);
}
static void* drawSlot=reinterpret_cast<void*>(&NativeDraw);
static void Require(bool good,const char* message){if(!good){std::puts(message);std::exit(1);}}
// PRODUCTION
int main(){
  std::memcpy(texture+0x78,"model_body",11);
  int w=256,h=512;std::memcpy(texture+0x68,&w,4);std::memcpy(texture+0x6C,&h,4);
  void* panel=panelData;
  for(int i=0;i<6;++i){
   *reinterpret_cast<void**>(panelData+0x230+i*0x25C+0x70)=sceneData[i];
   *reinterpret_cast<void**>(sceneData[i]+0x80)=managers[i];
   *reinterpret_cast<void**>(managers[i]+8)=lightLists[i];lightLists[i][0]=lights[i];
  }
  K1ClassModelTrace::Install(panel);
  Require(drawSlot==reinterpret_cast<void*>(&K1ClassModelTrace::TracedDraw),"Trace not installed");
  auto installedRows=messages.size();
  for(int i=0;i<3;++i) K1ClassModelTrace::TracedDraw(panel,nullptr,0.125f);
  Require(messages.size()==installedRows,"Trace performed file logging during the first three draws");
  K1ClassModelTrace::TracedDraw(panel,nullptr,0.125f);
  K1ClassModelTrace::TracedDraw(panel,nullptr,0.125f);
  Require(calls==5&&seenDelta==0.125f,"Native Draw not delegated exactly once");
  Require(K1ClassModelTrace::frame==4,"Trace not bounded to four frames");
  int frames=0,scenes=0;bool sawPending=false,sawTexture=false,sawLights=false;
  for(const auto& m:messages){if(m.find("class-model frame=")==0)++frames;
    if(m.find("class-scene frame=")==0)++scenes;
    sawLights|=m.find("lights=0->1")!=std::string::npos;
    sawPending|=m.find("pending=0->3")!=std::string::npos;
    sawTexture|=m.find("texture=model_body")!=std::string::npos;}
  Require(frames==4&&sawPending&&sawTexture,"Missing before/after texture evidence");
  Require(scenes==24&&viewCalls==30&&sawLights,"Missing per-model scene evidence or duplicate view draw");
  unsigned zero=0;Require(!std::memcmp(texture+0x58,&zero,4),"Trace mutated texture state");
  level=0;auto rows=messages.size();K1ClassModelTrace::TracedDraw(panel,nullptr,0.25f);
  Require(calls==6&&seenDelta==0.25f&&messages.size()==rows,"Disabled trace changed Draw");
  level=2;drawSlot=reinterpret_cast<void*>(0x12345678);K1ClassModelTrace::Install(panel);
  Require(drawSlot==reinterpret_cast<void*>(0x12345678),"Another patch's Draw was overwritten");
  std::puts("PASS: native class/model draws delegated once; first three draws buffered without file logging; 24 scene records and light transitions captured; texture data and other patches intact");
}
'''
    cpp = out / 'class-model-trace.cpp'
    cpp.write_text(harness.replace('// PRODUCTION', production), encoding='utf-8')
    build = (ROOT / 'src/controller-native/build_controller_standalone.cmd').read_text(encoding='utf-8')
    vc = re.search(r'^set VC=(.+)$', build, re.M).group(1).strip()
    exe = out / 'class-model-trace.exe'
    args = ['cl', '/nologo', '/O2', '/std:c++17', '/EHsc', '/Isrc/controller-native', str(cpp),
            '/Fo' + str(out) + '/', '/Fe' + str(exe)]
    cmd = out / 'build.cmd'
    cmd.write_text('@echo off\ncall "' + vc + '" x86 >nul\nif errorlevel 1 exit /b %errorlevel%\n'
                   + subprocess.list2cmdline(args) + '\nif errorlevel 1 exit /b %errorlevel%\n'
                   + subprocess.list2cmdline([str(exe)]) + '\n', encoding='utf-8')
    return subprocess.run(['cmd', '/d', '/c', str(cmd)], cwd=ROOT).returncode


if __name__ == '__main__':
    raise SystemExit(main())
