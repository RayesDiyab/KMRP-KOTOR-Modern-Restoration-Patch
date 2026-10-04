#pragma once
// Called on the GUI thread before native SetSize rebuilds panels and fonts.
bool KmrpRuntimeEngineDimensions(int width, int height);
bool KmrpRuntimeEngineReady();
// Whether controller support is on: the options package with its controller option
// on, or left at its default by a KOTOR Patch Manager that has no options.
bool KmrpControllerOptionK1();
