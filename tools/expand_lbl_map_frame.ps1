param(
    [Parameter(Mandatory = $true)]
    [string]$SourcePng,
    [Parameter(Mandatory = $true)]
    [string]$OutputPng
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

function New-RoundedRectanglePath {
    param(
        [System.Drawing.RectangleF]$Bounds,
        [float]$Radius
    )

    $diameter = $Radius * 2
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $path.AddArc($Bounds.Left, $Bounds.Top, $diameter, $diameter, 180, 90)
    $path.AddArc($Bounds.Right - $diameter, $Bounds.Top, $diameter, $diameter, 270, 90)
    $path.AddArc($Bounds.Right - $diameter, $Bounds.Bottom - $diameter, $diameter, $diameter, 0, 90)
    $path.AddArc($Bounds.Left, $Bounds.Bottom - $diameter, $diameter, $diameter, 90, 90)
    $path.CloseFigure()
    return $path
}

function New-ReadoutGlyphBitmap {
    param(
        [System.Drawing.Bitmap]$Source,
        [System.Drawing.Rectangle]$SourceBounds
    )

    $glyphs = New-Object System.Drawing.Bitmap(
        $SourceBounds.Width,
        $SourceBounds.Height,
        [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    for ($y = 0; $y -lt $SourceBounds.Height; $y++) {
        for ($x = 0; $x -lt $SourceBounds.Width; $x++) {
            $color = $Source.GetPixel($SourceBounds.X + $x, $SourceBounds.Y + $y)
            $cyan = $color.B -ge 105 -and $color.G -ge 60 -and ($color.B - $color.R) -ge 25
            $pink = $color.R -ge 105 -and $color.B -ge 70 -and ($color.R - $color.G) -ge 12
            $green = $color.G -ge 85 -and $color.R -le 115 -and ($color.G - $color.B) -ge 5
            if ($cyan -or $pink -or $green) {
                $brightest = [Math]::Max($color.R, [Math]::Max($color.G, $color.B))
                $alpha = [Math]::Min(255, [Math]::Max(0, ($brightest - 72) * 3))
                $glyphs.SetPixel($x, $y,
                    [System.Drawing.Color]::FromArgb($alpha, $color.R, $color.G, $color.B))
            }
        }
    }
    return $glyphs
}

$source = [System.Drawing.Bitmap]::FromFile((Resolve-Path -LiteralPath $SourcePng).Path)
$output = New-Object System.Drawing.Bitmap($source.Width, $source.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$graphics = [System.Drawing.Graphics]::FromImage($output)

try {
    $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
    $graphics.DrawImageUnscaled($source, 0, 0)
    $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

    # Remove only the former 616 x 296 frame. These source offsets follow the
    # underlying holographic grid cadence so the repaired area remains quiet.
    $graphics.DrawImage($source,
        (New-Object System.Drawing.Rectangle(1468, 800, 642, 46)),
        1468, 754, 642, 46, [System.Drawing.GraphicsUnit]::Pixel)
    $graphics.DrawImage($source,
        (New-Object System.Drawing.Rectangle(1468, 1074, 642, 44)),
        1468, 1030, 642, 44, [System.Drawing.GraphicsUnit]::Pixel)
    $graphics.DrawImage($source,
        (New-Object System.Drawing.Rectangle(1468, 800, 46, 318)),
        1428, 800, 46, 318, [System.Drawing.GraphicsUnit]::Pixel)
    $graphics.DrawImage($source,
        (New-Object System.Drawing.Rectangle(2064, 800, 46, 318)),
        2110, 800, 46, 318, [System.Drawing.GraphicsUnit]::Pixel)

    # Give both side readouts matching quiet gutters. This also clears the
    # exposed portions of the old right readout and both large arcs.
    $leftGutter = New-Object System.Drawing.RectangleF(300, 344, 395, 770)
    $rightGutter = New-Object System.Drawing.RectangleF(2172, 344, 395, 770)
    $gutterBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 0, 8, 25))
    try {
        $graphics.FillRectangle($gutterBrush, $leftGutter)
        $graphics.FillRectangle($gutterBrush, $rightGutter)
    }
    finally {
        $gutterBrush.Dispose()
    }

    # The engine preserves the module-map artwork aspect inside the much wider
    # LBL_Map control. The visible map is approximately 858..2576 x 370..1090
    # on a 3440 x 1440 screen. Map those bounds back to this 2867 x 1434 texture
    # and add a small, even visual margin instead of framing the full control.
    $outerBounds = New-Object System.Drawing.RectangleF(695, 344, 1477, 770)
    $innerBounds = New-Object System.Drawing.RectangleF(713, 362, 1441, 734)
    $outerPath = New-RoundedRectanglePath $outerBounds 22
    $innerPath = New-RoundedRectanglePath $innerBounds 14

    # Replace everything inside the new frame with a clean holographic field.
    # This removes the two original readouts and both oversized parenthesis arcs
    # without leaving tiled seams. The game map is drawn over this field.
    $graphics.SetClip($outerPath)
    $fieldBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 0, 8, 25))
    try {
        $graphics.FillRectangle($fieldBrush, $outerBounds)
    }
    finally {
        $fieldBrush.Dispose()
    }

    foreach ($glowStep in 1..9) {
        $insetX = 55 * $glowStep
        $insetY = 28 * $glowStep
        $glowAlpha = 8 + $glowStep
        $glowBrush = New-Object System.Drawing.SolidBrush(
            [System.Drawing.Color]::FromArgb($glowAlpha, 0, 79, 143))
        try {
            $graphics.FillEllipse($glowBrush,
                $outerBounds.X + $insetX,
                $outerBounds.Y + $insetY,
                $outerBounds.Width - (2 * $insetX),
                $outerBounds.Height - (2 * $insetY))
        }
        finally {
            $glowBrush.Dispose()
        }
    }

    $minorGrid = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(58, 0, 68, 118), 1)
    $majorGrid = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(78, 0, 83, 139), 1)
    try {
        $gridIndex = 0
        for ($x = 695; $x -le 2172; $x += 22) {
            $graphics.DrawLine($(if (($gridIndex % 5) -eq 0) { $majorGrid } else { $minorGrid }),
                $x, 344, $x, 1114)
            $gridIndex++
        }
        $gridIndex = 0
        for ($y = 344; $y -le 1114; $y += 22) {
            $graphics.DrawLine($(if (($gridIndex % 5) -eq 0) { $majorGrid } else { $minorGrid }),
                695, $y, 2172, $y)
            $gridIndex++
        }
    }
    finally {
        $minorGrid.Dispose()
        $majorGrid.Dispose()
        $graphics.ResetClip()
    }

    $outerGlow = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(70, 0, 82, 172), 13)
    $outerDark = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(235, 0, 33, 72), 8)
    $outerBlue = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(255, 2, 80, 152), 4)
    $outerHighlight = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(245, 0, 121, 204), 2)
    $innerDark = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(230, 0, 31, 68), 7)
    $innerBlue = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(255, 1, 70, 137), 3)
    $innerHighlight = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(220, 0, 105, 184), 1)

    try {
        $graphics.DrawPath($outerGlow, $outerPath)
        $graphics.DrawPath($outerDark, $outerPath)
        $graphics.DrawPath($outerBlue, $outerPath)
        $graphics.DrawPath($outerHighlight, $outerPath)
        $graphics.DrawPath($innerDark, $innerPath)
        $graphics.DrawPath($innerBlue, $innerPath)
        $graphics.DrawPath($innerHighlight, $innerPath)
    }
    finally {
        $outerGlow.Dispose()
        $outerDark.Dispose()
        $outerBlue.Dispose()
        $outerHighlight.Dispose()
        $innerDark.Dispose()
        $innerBlue.Dispose()
        $innerHighlight.Dispose()
    }

    # Rebuild both readouts as contained cards. Only the bright glyph pixels are
    # carried over, so neither card contains a mismatched miniature grid.
    $leftCardBounds = New-Object System.Drawing.RectangleF(455, 465, 220, 345)
    $leftCardPath = New-RoundedRectanglePath $leftCardBounds 12
    $leftCardBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(238, 0, 20, 47))
    $leftCardBorder = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(220, 0, 99, 171), 2)
    $leftGlyphs = New-ReadoutGlyphBitmap $source (New-Object System.Drawing.Rectangle(970, 480, 290, 455))
    $rightCardBounds = New-Object System.Drawing.RectangleF(2190, 470, 270, 114)
    $rightCardPath = New-RoundedRectanglePath $rightCardBounds 9
    $rightCardBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(238, 0, 20, 47))
    $rightCardBorder = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(220, 0, 99, 171), 2)
    $rightGlyphs = New-ReadoutGlyphBitmap $source (New-Object System.Drawing.Rectangle(1785, 475, 350, 150))
    try {
        $graphics.FillPath($leftCardBrush, $leftCardPath)
        $graphics.SetClip($leftCardPath)
        $graphics.DrawImage($leftGlyphs, (New-Object System.Drawing.Rectangle(469, 480, 192, 315)))
        $graphics.ResetClip()
        $graphics.DrawPath($leftCardBorder, $leftCardPath)

        $graphics.FillPath($rightCardBrush, $rightCardPath)
        $graphics.SetClip($rightCardPath)
        $graphics.DrawImage($rightGlyphs, (New-Object System.Drawing.Rectangle(2200, 480, 250, 94)))
        $graphics.ResetClip()
        $graphics.DrawPath($rightCardBorder, $rightCardPath)
    }
    finally {
        $leftGlyphs.Dispose()
        $leftCardBrush.Dispose()
        $leftCardBorder.Dispose()
        $leftCardPath.Dispose()
        $rightGlyphs.Dispose()
        $rightCardBrush.Dispose()
        $rightCardBorder.Dispose()
        $rightCardPath.Dispose()
        $outerPath.Dispose()
        $innerPath.Dispose()
    }

    $output.Save($OutputPng, [System.Drawing.Imaging.ImageFormat]::Png)
}
finally {
    $graphics.Dispose()
    $output.Dispose()
    $source.Dispose()
}

Write-Output "Wrote $OutputPng"
