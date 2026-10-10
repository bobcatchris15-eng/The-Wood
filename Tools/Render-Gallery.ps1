param([int]$Seed=42)
# Renders every review view via Render-Review.ps1 into Saved/Review/gallery/<view>.png and writes gallery/index.html.
# A frame whose luminance is flat (cold shader cache) or black is re-rendered once; the status column records what remained.
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
$gallery=Join-Path $taskRoot 'Saved/Review/gallery'
New-Item -ItemType Directory -Force -Path $gallery | Out-Null
Add-Type -AssemblyName System.Drawing

$views=[ordered]@{
 TemperateForest='Biome TemperateForest: nearest core to explorer start'
 OldGrowth='Biome OldGrowthForest: lattice search for core weight 0.85+'
 ColdRainforest='Biome ColdRainforest: lattice search for core weight 0.85+'
 WarmRainforest='Biome WarmRainforest: lattice search for core weight 0.85+'
 Taiga='Biome Taiga: lattice region (0,-1)'
 IcyHills='Biome IcyHills: lattice search for core weight 0.85+'
 RockyHighlands='Biome RockyHighlands: nearest core to explorer start'
 DryGrassland='Biome DryGrassland: nearest core to explorer start'
 Prairie='Biome Prairie: nearest core to explorer start'
 Savannah='Biome Savannah: lattice search for core weight 0.85+'
 Swamp='Biome Swamp: lattice search for core weight 0.85+'
 Marsh='Biome Marsh: lattice search for core weight 0.85+'
 Ruins='Ruins: nearest discovery, camera 12 m away facing it'
 Landmark='Landmark: nearest lattice landmark, camera 120 m away'
 Creature='Creature: first fauna spawn, camera 8 m away'
 Unreal='Unreal: nearest unreal-flagged region origin'
 Rain='Rain: forced WoodWeather rain 0.8 at wilderness start'
 Snow='Snow: forced WoodWeather snow 0.8 in IcyHills core'
}

function Get-Luma($path) {
  $bmp=[System.Drawing.Bitmap]::FromFile($path)
  try {
    $n=0; $sum=0.0; $sq=0.0
    for($y=0;$y -lt $bmp.Height;$y+=12) { for($x=0;$x -lt $bmp.Width;$x+=12) {
      $c=$bmp.GetPixel($x,$y); $l=0.299*$c.R+0.587*$c.G+0.114*$c.B
      $n++; $sum+=$l; $sq+=$l*$l
    } }
    $mean=$sum/$n
    [pscustomobject]@{Mean=$mean; SD=[math]::Sqrt([math]::Max(0,$sq/$n-$mean*$mean))}
  } finally { $bmp.Dispose() }
}

$rows=@()
foreach($v in $views.Keys) {
  $src=Join-Path $taskRoot "Saved/Review/$Seed-$v-0.png"
  $status='BROKEN'; $attempt=0
  while($status -eq 'BROKEN' -and $attempt -lt 2) {
    $attempt++
    Remove-Item -LiteralPath $src -ErrorAction SilentlyContinue
    & powershell -NoProfile -File (Join-Path $PSScriptRoot 'Render-Review.ps1') -Seed $Seed -View $v | Out-Null
    if($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $src)) { $status="BROKEN: render failed (attempt $attempt)"; continue }
    $s=Get-Luma $src
    if($s.Mean -lt 10) { $status="BROKEN: black (mean $([math]::Round($s.Mean)))" }
    elseif($s.SD -lt 6) { $status="BROKEN: flat grey (sd $([math]::Round($s.SD,1)), attempt $attempt)" }
    else { $status='OK' }
  }
  if(Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src -Destination (Join-Path $gallery "$v.png") -Force }
  $rows+=[pscustomobject]@{View=$v; Caption=$views[$v]; Status=$status}
  Write-Output "$v | $status"
}

$html=New-Object System.Text.StringBuilder
[void]$html.AppendLine('<!doctype html><html><head><meta charset="utf-8"><title>The Wood review gallery (seed ' + $Seed + ')</title>')
[void]$html.AppendLine('<style>body{font-family:sans-serif;background:#222;color:#eee;margin:16px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}figure{margin:0;background:#333;padding:6px}img{width:100%;display:block}figcaption{font-size:14px;margin-top:4px}.bad{color:#f66}</style></head><body>')
[void]$html.AppendLine("<h1>The Wood review gallery, seed $Seed</h1><div class=`"grid`">")
foreach($r in $rows) {
  $cls=if($r.Status -eq 'OK'){''}else{' class="bad"'}
  [void]$html.AppendLine("<figure><img src=`"$($r.View).png`" alt=`"$($r.View)`"><figcaption><b>$($r.View)</b>: $([System.Net.WebUtility]::HtmlEncode($r.Caption))<br><span$cls>$([System.Net.WebUtility]::HtmlEncode($r.Status))</span></figcaption></figure>")
}
[void]$html.AppendLine('</div></body></html>')
Set-Content -LiteralPath (Join-Path $gallery 'index.html') -Value $html.ToString() -Encoding UTF8

$broken=@($rows | Where-Object { $_.Status -ne 'OK' })
Write-Output "GALLERY: $($rows.Count) views, $($broken.Count) broken"
