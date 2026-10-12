/*
  KMRP for macOS, the Mac App Store's game: the game's window made to cover the display.

  With "Full screen" chosen in Aspyr's launcher, Steam's game covers the display. The App
  Store's game (1.4.1) does not: its own settings say full screen (Data.json,
  ASL_DisplayFullScreen true) and it opens an ordinary window with a title bar, 1024x768
  without KMRP and the display's size cut to what fits under the menu bar with it (measured
  2026-10-12, macOS 27, docs/macos-app-store.md, section 7.5). So KMRP does it here: the
  game's window loses its title bar, takes the display's frame, and the menu bar and the Dock
  are hidden while the game is in front.

  What the player chose is read once, before main, from the preference Aspyr's launcher has
  just written (DisplayFullScreen; the game moves it into Data.json and deletes it soon
  after). "In a window" there leaves the game alone.
*/
#import <AppKit/AppKit.h>
#include <dlfcn.h>
#include <mach-o/dyld.h>

static BOOL gWanted;
static int gApplied;
static NSTimeInterval gAppliedAt;

// Aspyr's window object keeps how many game pixels a point of the window is, worked out for the
// window it opened. KMRP's module asks for it again when told (kmrp-assets/resolution.cpp).
static void TellKmrp(void) {
    static void (*changed)(void);
    if (!changed) {
        for (uint32_t i = 0; i < _dyld_image_count(); i++) {
            const char* name = _dyld_get_image_name(i);
            const size_t length = name ? strlen(name) : 0;
            if (length < 11 || strcmp(name + length - 11, "/kmrp.dylib") != 0) continue;
            void* handle = dlopen(name, RTLD_NOLOAD | RTLD_NOW);
            if (handle) changed = (void (*)(void))dlsym(handle, "KMRP_WindowChanged");
            break;
        }
    }
    if (changed) changed();
    else fprintf(stderr, "[kmrp-loader] full screen: KMRP's module was not told (the mouse may be off)\n");
}

static NSWindow* GameWindow(void) {
    for (NSWindow* window in NSApp.windows)
        if (window.visible && window.contentView && window.frame.size.width >= 600 && window.frame.size.height >= 400)
            return window;
    return nil;
}

static void Cover(void) {
    NSWindow* window = GameWindow();
    if (!window) return;
    NSScreen* screen = window.screen ?: NSScreen.mainScreen;
    if (!screen) return;
    const BOOL titled = (window.styleMask & NSWindowStyleMaskTitled) != 0;
    if (window.styleMask & NSWindowStyleMaskFullScreen) return;   // the player's own green button
    if (!titled && NSEqualRects(window.frame, screen.frame)) return;
    // A window that will not stay covered is left to the game after a few tries in a row. A
    // change of resolution in the game sizes the window again, and it is covered again.
    const NSTimeInterval now = NSProcessInfo.processInfo.systemUptime;
    if (now - gAppliedAt > 5) gApplied = 0;
    if (gApplied >= 8) return;
    gApplied++;
    gAppliedAt = now;
    const NSRect before = window.frame;
    NSApp.presentationOptions = NSApplicationPresentationHideDock | NSApplicationPresentationHideMenuBar;
    window.styleMask = NSWindowStyleMaskBorderless;
    [window setFrame:screen.frame display:YES];
    [window makeKeyAndOrderFront:nil];
    [window makeFirstResponder:window.contentView];
    TellKmrp();
    fprintf(stderr, "[kmrp-loader] full screen: the window %.0fx%.0f%s now covers the display, %.0fx%.0f (%d)\n",
            before.size.width, before.size.height, titled ? " with a title bar" : "",
            screen.frame.size.width, screen.frame.size.height, gApplied);
}

void KmrpAppStoreFullscreenStart(void) {
    CFPropertyListRef value = CFPreferencesCopyAppValue(CFSTR("DisplayFullScreen"), kCFPreferencesCurrentApplication);
    gWanted = !value || (CFGetTypeID(value) == CFBooleanGetTypeID() ? CFBooleanGetValue(value)
                         : CFGetTypeID(value) == CFNumberGetTypeID() ? ![(__bridge NSNumber*)value isEqual:@0] : YES);
    if (value) CFRelease(value);
    fprintf(stderr, "[kmrp-loader] Aspyr's launcher: %s\n", gWanted ? "full screen" : "in a window, left as it is");
    if (!gWanted) return;
    dispatch_source_t timer = dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0, dispatch_get_main_queue());
    dispatch_source_set_timer(timer, dispatch_time(DISPATCH_TIME_NOW, NSEC_PER_SEC), NSEC_PER_SEC / 2, NSEC_PER_SEC / 10);
    dispatch_source_set_event_handler(timer, ^{ Cover(); });
    dispatch_resume(timer);
    (void)CFBridgingRetain(timer);
}
