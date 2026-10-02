#!/usr/bin/env python3
"""Execute the shipped x86_64 REPLACE payloads on macOS (Rosetta supported).
Checks clean SHA/guards, whole-instruction cuts, boundaries, alias ownership,
register/flag preservation and package inclusion. No live game is touched.
"""
import argparse
import hashlib
import subprocess
import tempfile
import tomllib
import zipfile
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / 'macos/patches/kmrp-layout/kotor1-steam-aspyr-macos.hooks.toml'
SITES = (0x1001d0663, 0x1001fa2bf, 0x1001e00cd, 0x1001e1627)
SHA = 'c1fcb8d37c702849882a17751c63ee0af7c2b9cbbc3b31b98a5f0edbc27c6d71'

RUNNER = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <sys/mman.h>
#include "payloads.h"
static void* code(const unsigned char* data, size_t size) {
    void* p = mmap(nullptr, 4096, PROT_READ|PROT_WRITE|PROT_EXEC,
                   MAP_PRIVATE|MAP_ANON, -1, 0);
    assert(p != MAP_FAILED);
    memcpy(p, data, size);
    static_cast<unsigned char*>(p)[size] = 0xc3; // KPM resume represented by RET
    return p;
}
int main() {
    // Relocate only the two absolute operands to test-owned data/code. Fixed
    // mappings at game addresses are refused in the standalone Rosetta process.
    unsigned char shadow[] = {0x41,0xba,1,0,0,0,0xc3};
    void* shadowCode = code(shadow,sizeof shadow);
    uint32_t storage = 0;
    auto* maximum = &storage;
    void* insertion = code(payload0, sizeof payload0);
    void* saturation = code(payload1, sizeof payload1);
    uintptr_t expectedShadow, expectedGlobal;
    memcpy(&expectedShadow,static_cast<unsigned char*>(insertion)+10,8);
    memcpy(&expectedGlobal,static_cast<unsigned char*>(saturation)+3,8);
    assert(expectedShadow == 0x1001d067b && expectedGlobal == 0x100635ba8);
    memcpy(static_cast<unsigned char*>(insertion)+10,&shadowCode,8);
    memcpy(static_cast<unsigned char*>(saturation)+3,&maximum,8);
    for (uint32_t id : {0u,1u,4998u,4999u,5000u,5001u,0x7fffffffu,0x80000000u,0xffffffffu}) {
        uint64_t value = id, marker;
        asm volatile("xor %%r10d,%%r10d; call *%2; mov %%r10,%1"
            : "+a"(value), "=r"(marker) : "r"(insertion) : "r10", "cc", "memory");
        assert(value == (id < 5000 ? uint64_t(id)*16 : id));
        assert(marker == (id >= 5000));
        *maximum = id;
        uint64_t before, after, result;
        asm volatile("cmp $1,%%eax; pushfq; pop %0; call *%3; pushfq; pop %1"
            : "=&r"(before), "=&r"(after), "=a"(result)
            : "r"(saturation), "a"(id) : "cc", "memory");
        assert(result == (id < 5000 ? id : 4999));
        assert(before == after);
    }
    alignas(8) unsigned char bin[0x88] = {};
    for (void* cleanup : {code(payload2,sizeof payload2), code(payload3,sizeof payload3)}) {
        for (uintptr_t primary : {uintptr_t(0),uintptr_t(0x12345000)}) {
            for (uintptr_t alias : {uintptr_t(0),primary,uintptr_t(0x56789000)}) {
                memcpy(bin+0x38,&primary,8); memcpy(bin+0x40,&alias,8);
                uintptr_t argument; unsigned char zero;
                asm volatile("call *%2; setz %1" : "=D"(argument), "=qm"(zero)
                    : "r"(cleanup), "b"(bin) : "cc", "memory");
                assert(argument == (alias == primary ? 0 : alias));
                assert(bool(zero) == (argument == 0)); // native JE decision
                assert(memcmp(bin+0x38,&primary,8)==0 && memcmp(bin+0x40,&alias,8)==0);
                // Native continuation deletes non-null argument, clears alias,
                // then deletes primary: aliased buffers must receive one delete.
                unsigned primaryDeletes = (argument && argument==primary) + bool(primary);
                assert(primaryDeletes == bool(primary));
                if (alias && alias != primary) assert(argument == alias);
            }
        }
    }
    puts("PASS: texture boundaries, shadow continuation, saturation flags, both grass alias/null/distinct cleanup paths");
}
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--kpatch', type=Path, action='append', default=[])
    args = parser.parse_args()
    clean = args.exe.read_bytes()
    assert len(clean) == 6333424 and hashlib.sha256(clean).hexdigest() == SHA
    # MH_PIE is absent: embedded preferred-VA pointers match the target's load convention.
    assert int.from_bytes(clean[24:28], 'little') & 0x200000 == 0
    hooks = {h['address']: h for h in tomllib.loads(HOOKS.read_text())['hooks']}
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    for site in SITES:
        h = hooks[site]
        assert h['type'] == 'replace'
        original = bytes(h['original_bytes'])
        assert clean[site-0x100000000:site-0x100000000+len(original)] == original
        assert sum(i.size for i in decoder.disasm(original,site)) == len(original)
        print(hex(site), ':', '; '.join(i.mnemonic+' '+i.op_str for i in decoder.disasm(bytes(h['replacement_bytes']),0)))
    for package in args.kpatch:
        with zipfile.ZipFile(package) as z:
            configs = [n for n in z.namelist() if n.endswith('.hooks.toml')]
            assert len(configs) == 1, configs
            shipped = {h['address']:h for h in tomllib.loads(z.read(configs[0]).decode())['hooks']}
            for site in SITES:
                for key in ('type','original_bytes','replacement_bytes'):
                    assert shipped[site][key] == hooks[site][key], (package,site,key)
        print('Package includes all guards:', package)
    with tempfile.TemporaryDirectory(prefix='kmrp-memory-test-') as folder:
        tmp = Path(folder)
        (tmp/'payloads.h').write_text('#include <initializer_list>\n'+'\n'.join(
            'static const unsigned char payload%d[] = {%s};' % (i,','.join(str(b) for b in hooks[s]['replacement_bytes']))
            for i,s in enumerate(SITES)))
        (tmp/'runner.cpp').write_text(RUNNER)
        subprocess.run(['clang++','-arch','x86_64','-std=c++17','-O0',str(tmp/'runner.cpp'),'-o',str(tmp/'runner')],check=True)
        subprocess.run([str(tmp/'runner')],check=True)
if __name__ == '__main__':
    main()
