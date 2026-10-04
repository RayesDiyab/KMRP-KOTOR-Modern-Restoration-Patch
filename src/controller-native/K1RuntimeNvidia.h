#pragma once

// What happened, for the caller that wants to tell cases apart (the test does).
enum class KmrpNvidiaPresent {
    Unavailable,     // no NVIDIA driver, or it would not answer: nothing to do
    AlreadyRight,    // Auto or Prefer native, or a value the game's profile holds itself
    LeftAlone,       // would show the defect, but the profile is not KMRP's to change
    Set,             // Prefer native written to the game's profile and read back
    Failed           // the check or the write failed; said so through `report`
};

// Keeps NVIDIA from presenting the game through a DXGI swap chain: the standalone
// module's copy of the installer's NvidiaPresentOperations.Install (KmrpPatcher.cs),
// with the same rules and the same record beside the game. `report` gets every line
// meant for the log. See docs/nvidia-present-method.md.
KmrpNvidiaPresent KmrpNvidiaPresentMethod(const wchar_t* executablePath, void (*report)(const char* line));

// The module's own use of it: once per process, off the game's threads, into KMRP's log.
void KmrpNvidiaPresentOnce();
