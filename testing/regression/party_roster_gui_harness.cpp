#include "K1PartyRosterGui.h"
#include <fstream>
#include <iterator>
#include <cstdio>
std::vector<unsigned char> Read(const char* path) {
    std::ifstream in(path,std::ios::binary);
    return {std::istreambuf_iterator<char>(in),std::istreambuf_iterator<char>()};
}
int main(int argc,char**argv) {
    if(argc!=4)return 2;
    std::vector<unsigned char> out;std::string reason;
    if(!(std::string(argv[1])=="--generate" ? KmrpGeneratePartyRosterGui(Read(argv[2]),out,reason) : KmrpBuildPartyRosterGui(Read(argv[1]),Read(argv[2]),out,reason))) {
        std::fprintf(stderr,"%s\n",reason.c_str());return 1;
    }
    std::ofstream file(argv[3],std::ios::binary);file.write(reinterpret_cast<const char*>(out.data()),out.size());
    return file?0:2;
}
