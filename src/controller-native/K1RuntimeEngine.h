#pragma once
// One line into kmrp-kpm.log.
void KmrpRuntimeLog(const char* line);
// Called on the GUI thread before native SetSize rebuilds panels and fonts.
bool KmrpRuntimeEngineDimensions(int width, int height);
bool KmrpRuntimeEngineReady();
// The engine's values written again at the size in force (the Icon Size slider's rows).
bool KmrpRuntimeEngineRefreshK1();
