Add-Type -AssemblyName System.Drawing

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$logoPath = Join-Path $root "assets\PBICompass-LOGO.png"
$outputPath = Join-Path $root "assets\linkedin-coming-soon.png"

$size = 1200
$bmp = New-Object System.Drawing.Bitmap $size, $size
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$g.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality

function Color-A($r, $g, $b, $a = 255) {
  return [System.Drawing.Color]::FromArgb($a, $r, $g, $b)
}

function New-RoundedPath($x, $y, $w, $h, $r) {
  $path = New-Object System.Drawing.Drawing2D.GraphicsPath
  $d = $r * 2
  $path.AddArc($x, $y, $d, $d, 180, 90)
  $path.AddArc($x + $w - $d, $y, $d, $d, 270, 90)
  $path.AddArc($x + $w - $d, $y + $h - $d, $d, $d, 0, 90)
  $path.AddArc($x, $y + $h - $d, $d, $d, 90, 90)
  $path.CloseFigure()
  return $path
}

function Draw-RoundedRect($x, $y, $w, $h, $r, $fill, $stroke, $strokeWidth = 1) {
  $path = New-RoundedPath $x $y $w $h $r
  $brush = New-Object System.Drawing.SolidBrush $fill
  $g.FillPath($brush, $path)
  $brush.Dispose()
  if ($strokeWidth -gt 0) {
    $pen = New-Object System.Drawing.Pen $stroke, $strokeWidth
    $g.DrawPath($pen, $path)
    $pen.Dispose()
  }
  $path.Dispose()
}

function Draw-Text($text, $font, $color, $x, $y, $w, $h, $align = "Near", $lineAlign = "Near") {
  $brush = New-Object System.Drawing.SolidBrush $color
  $fmt = New-Object System.Drawing.StringFormat
  $fmt.Alignment = [System.Drawing.StringAlignment]::$align
  $fmt.LineAlignment = [System.Drawing.StringAlignment]::$lineAlign
  $fmt.Trimming = [System.Drawing.StringTrimming]::EllipsisWord
  $rect = New-Object System.Drawing.RectangleF $x, $y, $w, $h
  $g.DrawString($text, $font, $brush, $rect, $fmt)
  $fmt.Dispose()
  $brush.Dispose()
}

$bgRect = New-Object System.Drawing.Rectangle 0, 0, $size, $size
$bg = New-Object System.Drawing.Drawing2D.LinearGradientBrush $bgRect, (Color-A 14 30 24), (Color-A 5 12 10), 90
$g.FillRectangle($bg, $bgRect)
$bg.Dispose()

$glow1 = New-Object System.Drawing.Drawing2D.GraphicsPath
$glow1.AddEllipse(-150, -120, 700, 520)
$brush1 = New-Object System.Drawing.Drawing2D.PathGradientBrush $glow1
$brush1.CenterColor = Color-A 99 196 160 88
$brush1.SurroundColors = @((Color-A 99 196 160 0))
$g.FillPath($brush1, $glow1)
$brush1.Dispose()
$glow1.Dispose()

$glow2 = New-Object System.Drawing.Drawing2D.GraphicsPath
$glow2.AddEllipse(640, 40, 720, 560)
$brush2 = New-Object System.Drawing.Drawing2D.PathGradientBrush $glow2
$brush2.CenterColor = Color-A 77 160 128 70
$brush2.SurroundColors = @((Color-A 77 160 128 0))
$g.FillPath($brush2, $glow2)
$brush2.Dispose()
$glow2.Dispose()

$glow3 = New-Object System.Drawing.Drawing2D.GraphicsPath
$glow3.AddEllipse(520, 710, 760, 560)
$brush3 = New-Object System.Drawing.Drawing2D.PathGradientBrush $glow3
$brush3.CenterColor = Color-A 114 218 177 72
$brush3.SurroundColors = @((Color-A 114 218 177 0))
$g.FillPath($brush3, $glow3)
$brush3.Dispose()
$glow3.Dispose()

for ($i = 0; $i -lt 1600; $i++) {
  $x = Get-Random -Minimum 0 -Maximum $size
  $y = Get-Random -Minimum 0 -Maximum $size
  $a = Get-Random -Minimum 5 -Maximum 16
  $c = Color-A 255 255 255 $a
  $p = New-Object System.Drawing.Pen $c, 1
  $g.DrawLine($p, $x, $y, $x + 1, $y)
  $p.Dispose()
}

Draw-RoundedRect 54 54 1092 1092 42 (Color-A 255 255 255 7) (Color-A 255 255 255 78) 2
Draw-RoundedRect 86 86 1028 1028 34 (Color-A 0 0 0 28) (Color-A 255 255 255 36) 1

$fontFamily = "Poppins"
$serifFamily = "Georgia"
$brandFont = New-Object System.Drawing.Font $fontFamily, 34, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
$tagFont = New-Object System.Drawing.Font $fontFamily, 20, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
$smallFont = New-Object System.Drawing.Font $fontFamily, 25, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
$headlineFont = New-Object System.Drawing.Font $fontFamily, 74, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
$headlineSerif = New-Object System.Drawing.Font $serifFamily, 82, ([System.Drawing.FontStyle]::Italic), ([System.Drawing.GraphicsUnit]::Pixel)
$bodyFont = New-Object System.Drawing.Font $fontFamily, 30, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
$metricFont = New-Object System.Drawing.Font $fontFamily, 48, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
$metricLabelFont = New-Object System.Drawing.Font $fontFamily, 21, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
$footerFont = New-Object System.Drawing.Font $fontFamily, 28, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)

$logo = [System.Drawing.Image]::FromFile($logoPath)
Draw-RoundedRect 112 112 88 88 24 (Color-A 255 255 255 238) (Color-A 255 255 255 95) 1
$g.DrawImage($logo, 125, 125, 62, 62)
$logo.Dispose()

Draw-Text "PBICompass" $brandFont (Color-A 255 255 255) 220 117 320 44 "Near" "Near"
Draw-RoundedRect 432 124 88 30 15 (Color-A 255 255 255 18) (Color-A 255 255 255 80) 1
Draw-Text "BETA" $tagFont (Color-A 255 255 255 222) 432 127 88 26 "Center" "Center"
Draw-RoundedRect 864 118 204 46 23 (Color-A 255 255 255 14) (Color-A 255 255 255 64) 1
Draw-Text "COMING SOON" $tagFont (Color-A 255 255 255 238) 864 124 204 34 "Center" "Center"

Draw-Text "Power BI documentation" $smallFont (Color-A 255 255 255 188) 118 258 800 42 "Near" "Near"
Draw-Text "without the" $headlineFont (Color-A 255 255 255) 118 307 750 90 "Near" "Near"
Draw-Text "manual grind." $headlineSerif (Color-A 226 255 243) 118 389 820 104 "Near" "Near"

Draw-Text "Save thousands of billing hours, dollars, and delivery time by turning reports into enterprise-ready documentation in minutes." $bodyFont (Color-A 255 255 255 208) 122 520 875 128 "Near" "Near"

$cardY = 700
$cardW = 305
$gap = 26
Draw-RoundedRect 118 $cardY $cardW 158 26 (Color-A 255 255 255 16) (Color-A 255 255 255 74) 1
Draw-RoundedRect (118 + $cardW + $gap) $cardY $cardW 158 26 (Color-A 255 255 255 16) (Color-A 255 255 255 74) 1
Draw-RoundedRect (118 + ($cardW + $gap) * 2) $cardY $cardW 158 26 (Color-A 255 255 255 16) (Color-A 255 255 255 74) 1

Draw-Text "1,000s" $metricFont (Color-A 255 255 255) 146 ($cardY + 32) 250 58 "Near" "Near"
Draw-Text "billing hours saved" $metricLabelFont (Color-A 255 255 255 188) 148 ($cardY + 94) 248 38 "Near" "Near"
Draw-Text '$$$' $metricFont (Color-A 255 255 255) (146 + $cardW + $gap) ($cardY + 32) 250 58 "Near" "Near"
Draw-Text "less documentation cost" $metricLabelFont (Color-A 255 255 255 188) (148 + $cardW + $gap) ($cardY + 94) 248 38 "Near" "Near"
Draw-Text "Minutes" $metricFont (Color-A 255 255 255) (146 + ($cardW + $gap) * 2) ($cardY + 32) 250 58 "Near" "Near"
Draw-Text "from PBIX to docs" $metricLabelFont (Color-A 255 255 255 188) (148 + ($cardW + $gap) * 2) ($cardY + 94) 248 38 "Near" "Near"

Draw-RoundedRect 118 930 964 108 30 (Color-A 255 255 255 230) (Color-A 255 255 255 255) 1
Draw-Text "The fastest Power BI documentation tool on the internet." $footerFont (Color-A 5 20 16) 150 956 900 44 "Center" "Near"
Draw-Text "AI-generated technical, audit, executive and user-guide docs." $metricLabelFont (Color-A 5 20 16 195) 150 1000 900 32 "Center" "Near"

$bmp.Save($outputPath, [System.Drawing.Imaging.ImageFormat]::Png)

$brandFont.Dispose()
$tagFont.Dispose()
$smallFont.Dispose()
$headlineFont.Dispose()
$headlineSerif.Dispose()
$bodyFont.Dispose()
$metricFont.Dispose()
$metricLabelFont.Dispose()
$footerFont.Dispose()
$g.Dispose()
$bmp.Dispose()

Write-Output $outputPath
