// Real x86 SDL virtual devices exercise the production adapter without a game.
// Only XInput and foreground detection are fakes, so no physical pad is moved.
#include "K1ControllerBackend.h"
#include <cstdio>
#include <cstdlib>
static XINPUT_STATE xbox{};
static bool xboxConnected = false;
static unsigned probes = 0, writes = 0;
static DWORD WINAPI FakeGetState(DWORD slot, XINPUT_STATE* s) {
    ++probes;
    if (slot || !xboxConnected) return ERROR_DEVICE_NOT_CONNECTED;
    *s = xbox; return ERROR_SUCCESS;
}
static DWORD WINAPI FakeSetState(DWORD, XINPUT_VIBRATION*) { ++writes; return ERROR_SUCCESS; }
static DWORD WINAPI FakeForeground(HWND, DWORD* pid) { *pid = GetCurrentProcessId(); return 1; }
#define XInputGetState FakeGetState
#define XInputSetState FakeSetState
#define GetWindowThreadProcessId FakeForeground
#include "../../src/controller-native/K1ControllerBackend.cpp"
#undef XInputGetState
#undef XInputSetState
#undef GetWindowThreadProcessId

static WORD receivedLow, receivedHigh;
static bool SDLCALL ReceiveRumble(void*, Uint16 low, Uint16 high) {
    receivedLow = low; receivedHigh = high; return true;
}
static void Check(bool ok, const char* label) {
    printf("%s %s\n", ok ? "PASS" : "FAIL", label);
    if (!ok) exit(1);
}
int main() {
    // The regression uses only process-local virtual devices. Environment hints
    // outrank SDL_SetHint, so the production initialization cannot open real HID.
    SetEnvironmentVariableA("SDL_JOYSTICK_HIDAPI", "0");
    XINPUT_STATE state{};
    ReadControllerK1(state);
    Check(sdlReady, "x86 SDL loads and initializes");
    unsigned baseline = probes;
    for (int i=0; i<50; ++i) ReadControllerK1(state);
    Check(probes == baseline, "missing XInput slots are not polled every frame");
    HMODULE lib = GetModuleHandleW(L"kmrp-sdl3.dll");
#define API(name) auto f##name = reinterpret_cast<decltype(&name)>(GetProcAddress(lib, #name)); Check(f##name != nullptr, #name)
    API(SDL_AttachVirtualJoystick); API(SDL_DetachVirtualJoystick);
    API(SDL_OpenJoystick); API(SDL_CloseJoystick);
    API(SDL_SetJoystickVirtualAxis); API(SDL_SetJoystickVirtualButton);
    API(SDL_GetHint);
    Check(strcmp(fSDL_GetHint(SDL_HINT_TIMER_RESOLUTION), "0") == 0, "timer resolution disabled");
    const Uint16 vendors[] = {0x054c, 0x057e, 0x28de};
    const Uint16 products[] = {0x0ce6, 0x2009, 0x1205};
    for (int family=1; family<=3; ++family) {
        SDL_VirtualJoystickDesc desc{};
        desc.version = sizeof(desc);
        desc.type = SDL_JOYSTICK_TYPE_GAMEPAD;
        desc.vendor_id = vendors[family-1]; desc.product_id = products[family-1];
        desc.naxes = 6; desc.nbuttons = 15;
        desc.axis_mask = 0x3f; desc.button_mask = 0x7fff;
        desc.name = "KMRP virtual regression"; desc.Rumble = ReceiveRumble;
        SDL_JoystickID id = fSDL_AttachVirtualJoystick(&desc);
        Check(id != 0, "virtual device attached");
        SDL_Joystick* joy = fSDL_OpenJoystick(id);
        Check(joy != nullptr, "virtual device opened");
        fSDL_SetJoystickVirtualAxis(joy, 4, -32768);
        fSDL_SetJoystickVirtualAxis(joy, 5, -32768);
        nextScan = 0;
        ReadControllerK1(state); ReadControllerK1(state);
        Check(ControllerXInputSlotK1() == -1 && ControllerSdlFamilyK1() == family, "physical device identity selects family");
        fSDL_SetJoystickVirtualButton(joy, SDL_GAMEPAD_BUTTON_SOUTH, true);
        fSDL_SetJoystickVirtualAxis(joy, 0, 16000);
        fSDL_SetJoystickVirtualAxis(joy, 1, -32768);
        fSDL_SetJoystickVirtualAxis(joy, 4, 32767);
        ReadControllerK1(state);
        Check(state.Gamepad.wButtons == XINPUT_GAMEPAD_A, "south maps to normalized A including Nintendo B position");
        Check(state.Gamepad.sThumbLX == 16000 && state.Gamepad.sThumbLY == 32767, "stick range and Y sign");
        Check(state.Gamepad.bLeftTrigger == 255 && state.Gamepad.bRightTrigger == 0, "trigger extrema");
        SetControllerRumbleK1(12345, 54321);
        Check(receivedLow == 12345 && receivedHigh == 54321, "rumble reaches active SDL device");
        Check(!SetControllerRumbleK1(12345, 54321), "unchanged rumble not resent each frame");
        xboxConnected = true; xbox.Gamepad.wButtons = XINPUT_GAMEPAD_B; nextScan = 0;
        ReadControllerK1(state);
        Check(ControllerXInputSlotK1() == 0 && state.Gamepad.wButtons == 0, "XInput activity takes ownership through neutral handoff");
        Check(receivedLow == 0 && receivedHigh == 0, "handoff stops old SDL motors");
        ReadControllerK1(state);
        Check(state.Gamepad.wButtons == XINPUT_GAMEPAD_B, "Xbox still uses XInput");
        Check(SetControllerRumbleK1(100, 200) && writes > 0, "Xbox rumble uses XInput");
        xboxConnected = false;
        fSDL_DetachVirtualJoystick(id);
        fSDL_CloseJoystick(joy);
        Check(!ReadControllerK1(state), "disconnect clears connection and state");
        Check(state.Gamepad.wButtons == 0, "no stuck button after disconnect");
    }
    puts("PASS SDL adapter regression");
}
