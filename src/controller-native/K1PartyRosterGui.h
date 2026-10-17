#pragma once
#include <string>
#include <vector>
// Adapt a supplied 32-slot / 16-per-page roster layout to the current KMRP GUI.
// The roster remains the source of IDs, navigation, captions and state. Inputs
// stay untouched. Unsupported or malformed layouts return false with no output.
bool KmrpBuildPartyRosterGui(const std::vector<unsigned char>& roster,
                            const std::vector<unsigned char>& kmrp,
                            std::vector<unsigned char>& output, std::string& reason);

// Generate the roster layout directly from this size's ordinary KMRP party GUI.
bool KmrpGeneratePartyRosterGui(const std::vector<unsigned char>& kmrp,
                               std::vector<unsigned char>& output,std::string& reason);
