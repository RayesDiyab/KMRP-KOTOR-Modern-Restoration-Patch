// Shared by KMRP's module (kmrp.dll) and the controller patch's (kmrp-controller.dll).
// Until 2026-10-31 this lived in K1ControllerLayout.cpp, which kmrp.dll then compiled whole, with
// the rest of the controller code, for it (issue 82, F1:
// docs/cleanup-1.6/F1-kmrp-without-controller-code.md).

#include "K1StatusSummary.h"
#include "K1GuiControls.h"
#include "KmrpOptions.h"

#include <windows.h>
#include <cstdio>

namespace {
using namespace KmrpGui;

// Is this control one of the panel's own? One of the nine rows, the net shift
// (LBL_NETSHIFT and its line), has no control in statussummary.gui, so binding
// left it out of the panel's array and the engine never draws it; such a row must
// not take a place.
bool boundTo(void* panel, void* control) {
    const int id=At<int>(control,0x50), count=At<int>(panel,0x24);
    void** const array=At<void**>(panel,0x20);
    return id>=0 && id<count && IsReadableK1(array,count*sizeof(void*)) && array[id]==control;
}

unsigned summaryLogs = 0;

void layoutStatusSummary(void* manager, void* panel) {
    if (!IsReadableK1(panel,K1_SUMMARY_OK+0x1C4) || !IsReadableK1(manager,0x70)) return;
    char* const base=static_cast<char*>(panel);
    int rows[K1_SUMMARY_ROWS]={};
    int count=0, widest=0, lineHeight=0;
    for (int i=0;i<K1_SUMMARY_ROWS;++i) {
        void* const icon=base+K1_SUMMARY_ICONS+i*K1_LABEL_SIZE;
        void* const line=base+K1_SUMMARY_LINES+i*K1_LABEL_SIZE;
        // The engine shows a row by setting its icon's visible bit (0x0062604x
        // and 0x00626245 clear it again).
        if (!(At<unsigned>(icon,0x44)&2u) || !boundTo(panel,icon) || !boundTo(panel,line))
            continue;
        int height=0;
        const int width=labelTextWidth(line,height);
        if (width<=0 || height<=0) continue;
        if (width>widest) widest=width;
        if (height>lineHeight) lineHeight=height;
        rows[count++]=i;
    }
    if (!count) return;
    // The 640x480 layout, in units of its own 16 px line.
    auto at16=[lineHeight](int v) { return (v*lineHeight+8)/16; };
    const int screenW=At<short>(manager,0x6C), screenH=At<short>(manager,0x6E);
    if (screenW<=0 || screenH<=0) return;
    const int lineX=at16(52);
    // The widest line as drawn, and a quarter of a line more: the art's border
    // sits on the box's edge, and text touching it read as clipped.
    int lineW=widest+lineHeight/4;
    int boxW=lineX+lineW+at16(10);
    if (boxW>screenW) { boxW=screenW; lineW=boxW-lineX-at16(10); }
    // Room for OK, the pad's A left of it and as much again on the right, so OK
    // stays centred; one short line would otherwise put the A on the box's edge.
    const int okW=at16(100), okH=at16(22);
    const int roomy=okW+2*(okH+okH/4+at16(4));
    if (boxW<roomy) boxW=roomy<screenW ? roomy : screenW;
    int y=at16(10);
    for (int n=0;n<count;++n) {
        void* const icon=base+K1_SUMMARY_ICONS+rows[n]*K1_LABEL_SIZE;
        void* const line=base+K1_SUMMARY_LINES+rows[n]*K1_LABEL_SIZE;
        const int iconRect[4]={at16(10),y,at16(32),at16(32)};
        const int lineRect[4]={lineX,y-at16(1),lineW,at16(32)};
        setExtentIfChanged(icon,iconRect);
        setExtentIfChanged(line,lineRect);
        y+=at16(37);
    }
    const int okY=y-at16(7);
    const int boxH=okY+at16(32);
    const int okRect[4]={(boxW-okW)/2,okY,okW,okH};
    const int boxRect[4]={(screenW-boxW)/2,(screenH-boxH)/2,boxW,boxH};
    setExtentIfChanged(base+K1_SUMMARY_OK,okRect);
    setExtentIfChanged(panel,boxRect);
    const bool badged=StatusSummaryBadgeK1(panel,okRect);
    if (KmrpDebugLogs() && summaryLogs<8) {
        ++summaryLogs;
        FILE* f=nullptr;
        if ((f = openLog()) != nullptr) {
            fprintf(f,"%lu status-summary rows=%d lineHeight=%d widest=%d box=(%d,%d,%d,%d) ok=(%d,%d,%d,%d) badge=%d\n",
                GetTickCount(),count,lineHeight,widest,boxRect[0],boxRect[1],boxRect[2],boxRect[3],
                okRect[0],okRect[1],okRect[2],okRect[3],badged?1:0);
            fclose(f);
        }
    }
}

// The status summary, wherever the manager holds it: its panel list or, while it
// waits for OK, its modal list.
void updateStatusSummary(void* manager) {
    if (!IsReadableK1(manager,0x9C)) return;
    const unsigned lists[2][2]={{0x88,0x8C},{0x94,0x98}};
    for (const auto& list: lists) {
        void** const panels=At<void**>(manager,list[0]);
        const int count=At<int>(manager,list[1]);
        if (count<=0 || count>256 || !IsReadableK1(panels,count*sizeof(void*))) continue;
        for (int i=0;i<count;++i) {
            void* const panel=panels[i];
            if (IsReadableK1(panel,4) && At<std::uintptr_t>(panel,0)==K1_STATUS_SUMMARY_VTABLE) {
                layoutStatusSummary(manager,panel);
                return;
            }
        }
    }
}

}  // namespace

// The status summary's layout. KMRP's GUI frame (KmrpCoreGuiWorkK1) and the controller
// patch's (ControllerLayoutFrameK1) both call it, so with both patches it runs twice a frame;
// it sets an extent only when it differs, so the second pass changes nothing (F1 report).
void StatusSummaryFrameK1(void* manager) {
    updateStatusSummary(manager);
}
