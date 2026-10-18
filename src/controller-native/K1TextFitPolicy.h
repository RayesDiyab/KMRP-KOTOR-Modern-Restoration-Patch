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
// As font dimensions decrease, native wrapping must have a monotone fit result.
// The return value is always the request or a verified positive smaller float.
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
    // reducing scale may remove a whole line. Find a real fitting bracket.
    const float minimum = (std::numeric_limits<float>::denorm_min)();
    for (int step = 0; step < 320; ++step) {
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

