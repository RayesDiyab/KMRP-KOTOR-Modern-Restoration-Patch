/* A picture resized as AbilityIconGenerator.Resize resizes it: linear, sampled at pixel
 * centres, as the C# does. For kmrp-abilityicons.c and kmrp-gameart.c (audit S-8). Needs the C
 * library's headers. NULL when there is no picture or no memory. */
#ifndef KMRP_IMAGE_H
#define KMRP_IMAGE_H

static inline uint8_t *resize(const uint8_t *pixels, int width, int height, int new_width, int new_height) {
    uint8_t *result = pixels ? malloc((size_t)new_width * new_height * 4) : NULL;
    if (!result) return NULL;
    double x_ratio = (double)width / new_width;
    double y_ratio = (double)height / new_height;
    for (int y = 0; y < new_height; y++) {
        double sy = (y + 0.5) * y_ratio - 0.5;
        int y0 = (int)sy;
        if (y0 > height - 1) y0 = height - 1;
        if (y0 < 0) y0 = 0;
        int y1 = y0 + 1 < height - 1 ? y0 + 1 : height - 1;
        double wy = sy - y0;
        if (wy < 0) wy = 0;
        for (int x = 0; x < new_width; x++) {
            double sx = (x + 0.5) * x_ratio - 0.5;
            int x0 = (int)sx;
            if (x0 > width - 1) x0 = width - 1;
            if (x0 < 0) x0 = 0;
            int x1 = x0 + 1 < width - 1 ? x0 + 1 : width - 1;
            double wx = sx - x0;
            if (wx < 0) wx = 0;
            int i00 = (y0 * width + x0) * 4, i01 = (y0 * width + x1) * 4;
            int i10 = (y1 * width + x0) * 4, i11 = (y1 * width + x1) * 4;
            int o = (y * new_width + x) * 4;
            for (int c = 0; c < 4; c++) {
                double top = pixels[i00 + c] * (1 - wx) + pixels[i01 + c] * wx;
                double bottom = pixels[i10 + c] * (1 - wx) + pixels[i11 + c] * wx;
                result[o + c] = (uint8_t)(top * (1 - wy) + bottom * wy + 0.5);
            }
        }
    }
    return result;
}

#endif
