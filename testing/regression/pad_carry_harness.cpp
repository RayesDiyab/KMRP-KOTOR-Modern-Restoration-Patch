// K1PadCarry.h on the sequences a movie's end can give, with the edges the buffer would emit.
// Test-PadCarry.py builds this. The case of the maintainer's report is "held through the end".
#include "K1PadCarry.h"

#include <cstdio>
#include <string>
#include <vector>

namespace {

constexpr std::uint16_t A = 0x1000, B = 0x2000, Start = 0x0010, LeftTrigger = 0x0400;

struct Reader {
    KmrpPadCarry carry;
    std::uint16_t last = 0;
    std::string edges;

    // One poll: what FillNativeJoystickBufferK1 does with the word, its press and release records.
    void Poll(std::uint16_t word) {
        const std::uint16_t seen = carry.Filter(word);
        for (const std::uint16_t mask : {A, B, Start, LeftTrigger}) {
            const bool now = (seen & mask) != 0, was = (last & mask) != 0;
            if (now != was) {
                edges += now ? '+' : '-';
                edges += mask == A ? 'A' : mask == B ? 'B' : mask == Start ? 'S' : 'L';
            }
        }
        last = seen;
    }
};

int g_failed = 0;
void Check(const char* name, const std::string& got, const std::string& want)
{
    const bool ok = got == want;
    std::printf("%s %-46s %s\n", ok ? "ok  " : "FAIL", name, got.c_str());
    if (!ok) g_failed = 1;
}

}  // namespace

int main()
{
    {
        Reader r;
        r.carry.MovieFrame();
        r.Poll(A);
        r.Poll(A);
        r.Poll(0);
        Check("held through the end: no press, no release", r.edges, "");
        r.Poll(A);
        r.Poll(0);
        Check("the next press is a press", r.edges, "+A-A");
    }
    {
        Reader r;
        r.carry.MovieFrame();
        r.Poll(0);
        r.Poll(A);
        r.Poll(0);
        Check("let go before the first poll, then pressed", r.edges, "+A-A");
    }
    {
        Reader r;
        r.Poll(A);
        r.carry.MovieFrame();
        r.Poll(A);
        r.Poll(0);
        Check("the press that started the movie is released", r.edges, "+A-A");
    }
    {
        Reader r;
        r.Poll(A);
        r.carry.MovieFrame();
        r.Poll(0);
        Check("the same, let go during the movie", r.edges, "+A-A");
    }
    {
        Reader r;
        r.carry.MovieFrame();
        r.Poll(A | B);
        r.Poll(A);
        r.Poll(A | B);
        r.Poll(A);
        r.Poll(0);
        Check("two held: B pressed again is a press, A stays out", r.edges, "+B-B");
    }
    {
        Reader r;
        r.carry.MovieFrame();
        r.Poll(LeftTrigger);
        r.Poll(0);
        r.Poll(LeftTrigger);
        Check("a trigger is carried as a button is", r.edges, "+L");
    }
    {
        Reader r;
        r.carry.MovieFrame();
        r.carry.MovieFrame();
        r.Poll(Start);
        r.carry.MovieFrame();
        r.Poll(Start);
        r.Poll(0);
        Check("a second movie straight after", r.edges, "");
    }
    {
        Reader r;
        r.Poll(A);
        r.Poll(A);
        r.Poll(0);
        r.Poll(B);
        r.Poll(0);
        Check("no movie: every edge passes", r.edges, "+A-A+B-B");
    }
    return g_failed;
}
