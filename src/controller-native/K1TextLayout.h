#pragma once

// Shared per-native-string fitting. Font objects and the user's requested sizes
// are never changed to make one control fit.
void KmrpTextLayoutFrameK1(void* manager);
void KmrpTextLayoutFontsChangedK1();
void KmrpTextLayoutTrackPanelK1(void* panel, const char* resource);
void KmrpTextLayoutTrackControlK1(void* panel, void* control, const char* tag);
void KmrpTextLayoutForgetPanelK1(void* panel);
void KmrpTextLayoutForgetControlK1(void* control);

// A wrapper is native CSWGuiText, not CSWGuiTextParams or the owning control.
// Scrollable/expanding content keeps the requested scale. Layout adapters use
// native wrapping at the actual width and a ceiling of fractional draw bounds.
void KmrpTextFlowK1(void* wrapper);
void KmrpTextBoundedK1(void* wrapper);
void KmrpTextEditableK1(void* wrapper);
int KmrpTextNaturalHeightK1(void* wrapper);
double KmrpTextNaturalWidthK1(void* wrapper);
double KmrpTextNaturalLineHeightK1(void* wrapper);
unsigned KmrpTextLayoutGenerationK1();
