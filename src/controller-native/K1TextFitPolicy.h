#pragma once
#include <cmath>
#include <limits>

namespace KmrpTextFit {
struct Measurement { double width, height; int lines; bool valid; };
struct Bounds { double width, height; };

inline bool Valid(const Measurement& measured) {
    return measured.valid && std::isfinite(measured.width) && std::isfinite(measured.height)
        && measured.width >= 0.0 && measured.height >= 0.0 && measured.lines >= 0;
}
inline bool Fits(const Measurement& measured, Bounds bounds) {
    // The caller only submits nonempty strings. Native wrapping can produce
    // zero lines when even the first word cannot fit; that is not a success.
    return measured.lines > 0 && measured.width <= bounds.width && measured.height <= bounds.height;
}

// Measure must recompute the native wrap at the supplied absolute local scale.
// It must not change global font metrics. Invalid measurements abort fitting,
// so an unsupported native object retains its requested presentation.
// The return value is always the request or a verified positive smaller float:
// the largest scale below the request that fits, to within one step of the walk
// below, or exactly when nothing between fits.
//
// Native wrapping does not fit monotonically. The line breaker sums each glyph's
// advance truncated to a whole pixel (0x0045A2F0), while the drawn width, which
// Fits checks, is fractional; a line the breaker fills to the box's edge may then
// overrun it by a few pixels at one scale and fit at a slightly smaller one. Until
// 2026-10-19 the search halved the scale until something fitted and bisected below
// that: at 1440x1080 a Bastila subtitle that needed four lines was drawn on one
// line at a third of the text size, though three lines fitted at 89% of it (the
// maintainer's capture; reproduced with the 2.25 fnt_d16x16 metrics). It now walks
// down from the request in steps of 1/128 and refines below the first scale that
// fits; halving only takes over far below the request.
template<class Measure>
float Fit(float requestedScale, Bounds bounds, Measure measure) {
    if (!std::isfinite(requestedScale) || requestedScale <= 0.0f
        || !std::isfinite(bounds.width) || !std::isfinite(bounds.height)
        || bounds.width <= 0.0 || bounds.height <= 0.0) return requestedScale;
    Measurement current = measure(requestedScale);
    if (!Valid(current) || Fits(current, bounds)) return requestedScale;

    float upper = requestedScale;
    float lower = 0.0f;
    // A ratio based on the first line count cannot solve a wrapped string:
    // reducing scale may remove a whole line. Find a real fitting bracket, the
    // first fitting step down from the request (256 steps reach 13% of it).
    for (int step = 0; step < 256; ++step) {
        const float candidate = static_cast<float>(static_cast<double>(upper) * 127.0 / 128.0);
        if (!(candidate > 0.0f) || candidate >= upper) break;
        current = measure(candidate);
        if (!Valid(current)) return requestedScale;
        if (Fits(current, bounds)) { lower = candidate; break; }
        upper = candidate;
    }
    const float minimum = (std::numeric_limits<float>::denorm_min)();
    for (int step = 0; lower <= 0.0f && step < 320; ++step) {
        float candidate = upper * 0.5f;
        if (candidate < minimum) candidate = minimum;
        if (candidate >= upper) return requestedScale;
        current = measure(candidate);
        if (!Valid(current)) return requestedScale;
        if (Fits(current, bounds)) { lower = candidate; break; }
        upper = candidate;
    }
    if (lower <= 0.0f) return requestedScale;

    for (int step = 0; step < 20; ++step) {
        const double midpoint = static_cast<double>(lower)
            + (static_cast<double>(upper) - lower) * 0.5;
        float candidate = static_cast<float>(midpoint);
        // Conversion to float may round toward the failing upper boundary.
        if (static_cast<double>(candidate) > midpoint)
            candidate = std::nextafter(candidate, 0.0f);
        if (candidate <= lower || candidate >= upper) break;
        current = measure(candidate);
        if (!Valid(current)) return requestedScale;
        if (Fits(current, bounds)) lower = candidate;
        else upper = candidate;
    }
    // Verify the actual float sent back to the engine, never an unrounded
    // double threshold. The request is retained if measurement became invalid.
    current = measure(lower);
    return Valid(current) && Fits(current, bounds) ? lower : requestedScale;
}
}

