#!/usr/bin/env python3
"""Execute upstream SSE2 ceiling payloads from the shipped hook file (Mac/Rosetta)."""
from pathlib import Path
import argparse,hashlib,subprocess,tempfile,tomllib
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument('--exe',type=Path,required=True);args=parser.parse_args()
b=args.exe.read_bytes();assert hashlib.sha256(b).hexdigest()=='c1fcb8d37c702849882a17751c63ee0af7c2b9cbbc3b31b98a5f0edbc27c6d71'
hooks=tomllib.loads((ROOT/'macos/patches/kmrp-layout/kotor1-steam-aspyr-macos.hooks.toml').read_text())['hooks']
sites=(0x1001bc4a4,0x1001bc4ba,0x1001bc52c,0x1001bc5d1,0x1001bc091)
source=r'''
#include <cassert>
#include <cmath>
#include <cstring>
#include <cstdio>
#include <cstdint>
#include <sys/mman.h>
void test(const unsigned char* data,int size,int reg){
 void* code=mmap(nullptr,4096,7,MAP_PRIVATE|MAP_ANON,-1,0);assert(code!=MAP_FAILED);
 memcpy(code,data,size);((unsigned char*)code)[size]=0xc3;
 for(float input:{0.f,1.f,16.f,16.1f,27.0000019f,54.0000038f,81.0000076f,108.f,32760.1f}){
  float out;uint64_t before,after;alignas(16) unsigned char scratch[16],result[16];memset(scratch,0x5a,16);
  if(!reg){asm volatile("movdqu %[scratch],%%xmm2;movss %[input],%%xmm0;cmp $1,%%eax;pushfq;pop %[before];call *%[code];pushfq;pop %[after];movss %%xmm0,%[out];movdqu %%xmm2,%[result]": [out]"=m"(out),[before]"=&r"(before),[after]"=&r"(after),[result]"=m"(result):[scratch]"m"(scratch),[input]"m"(input),[code]"r"(code):"rax","xmm0","xmm2","cc","memory");}
  else{asm volatile("movdqu %[scratch],%%xmm2;movss %[input],%%xmm1;cmp $1,%%eax;pushfq;pop %[before];call *%[code];pushfq;pop %[after];movss %%xmm1,%[out];movdqu %%xmm2,%[result]": [out]"=m"(out),[before]"=&r"(before),[after]"=&r"(after),[result]"=m"(result):[scratch]"m"(scratch),[input]"m"(input),[code]"r"(code):"rax","xmm1","xmm2","cc","memory");}
  assert(out==std::ceil(input));assert(before==after);assert(!memcmp(scratch,result,16));
 }
 munmap(code,4096);
}
'''.replace('#include <cassert>','#include <initializer_list>\n#include <cassert>')
for i,addr in enumerate(sites):
 h=next(h for h in hooks if h['address']==addr);raw=bytes(h['original_bytes']);assert b[addr-0x100000000:addr-0x100000000+len(raw)]==raw
 assert sum(ins.size for ins in Cs(CS_ARCH_X86,CS_MODE_64).disasm(raw,addr))==len(raw)
 payload=bytes(h['replacement_bytes']);suffix=bytes.fromhex('f30f2cc0') if i==0 else bytes.fromhex('488b7dc0') if i==1 else b''
 if suffix:assert payload.endswith(suffix);payload=payload[:-len(suffix)]
 source+=f'unsigned char p{i}[]={{'+','.join(map(str,payload))+'};\n'
source+='int main(){'+''.join(f'test(p{i},sizeof p{i},{0 if i<2 or i==4 else 1});' for i in range(5))+'puts("PASS five native-height guards, SSE2 ceiling, flags and XMM2 preservation");}\n'
with tempfile.TemporaryDirectory(prefix='kmrp-native-height-') as folder:
 p=Path(folder);(p/'test.cpp').write_text(source);subprocess.run(['clang++','-arch','x86_64','-std=c++17','-O2',str(p/'test.cpp'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
