// KMRP for macOS: the status summary laid out at the font's size (status_summary.cpp), and the
// text measuring it needs, which the controller's dialogue A shares.
#pragma once

#include "text.h"

#include <cstddef>
#include <cstdint>

namespace kmrp {
namespace summary {

struct Result { void* panel; int rows, lineHeight, widest; int box[4], ok[4]; };

// Finds the status summary in the GUI manager's panel or modal list and lays it out; true and
// out filled when there was one with rows to lay out.
bool Update(void* manager, Result* out);

}  // namespace summary
}  // namespace kmrp
