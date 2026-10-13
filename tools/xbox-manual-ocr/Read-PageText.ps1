# Reads the text of page images with the recogniser built into Windows and
# writes one JSON file per image: every word with its box, in image pixels.
# Run with Windows PowerShell 5.1 (the WinRT types do not load in pwsh 7).
param(
    [Parameter(Mandatory)][string]$ImageDir,
    [Parameter(Mandatory)][string]$OutDir,
    [string]$Language = 'en-US'
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]

$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1

function Wait-Result($operation, [type]$type) {
    $task = $asTask.MakeGenericMethod($type).Invoke($null, @($operation))
    $task.Wait()
    $task.Result
}

$available = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages | ForEach-Object { $_.LanguageTag }
Write-Output ("languages: " + ($available -join ', '))
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new($Language))
if (-not $engine) { throw "no recogniser for $Language" }
Write-Output ("max image dimension: " + [Windows.Media.Ocr.OcrEngine]::MaxImageDimension)

New-Item -ItemType Directory -Force $OutDir | Out-Null
foreach ($file in Get-ChildItem $ImageDir -Filter *.png | Sort-Object Name) {
    $storage = Wait-Result ([Windows.Storage.StorageFile]::GetFileFromPathAsync($file.FullName)) ([Windows.Storage.StorageFile])
    $stream = Wait-Result ($storage.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Wait-Result ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Wait-Result ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Wait-Result ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

    $lines = foreach ($line in $result.Lines) {
        , @(foreach ($word in $line.Words) {
            $r = $word.BoundingRect
            [ordered]@{ t = $word.Text; x = $r.X; y = $r.Y; w = $r.Width; h = $r.Height }
        })
    }
    $page = [ordered]@{ width = $bitmap.PixelWidth; height = $bitmap.PixelHeight; lines = @($lines) }
    $json = ConvertTo-Json $page -Depth 6 -Compress
    [IO.File]::WriteAllText((Join-Path $OutDir ($file.BaseName + '.json')), $json, [Text.UTF8Encoding]::new($false))
    Write-Output ("{0}: {1} lines" -f $file.Name, @($lines).Count)
    $stream.Dispose()
}
