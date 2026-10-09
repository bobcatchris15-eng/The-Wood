$ErrorActionPreference = 'Stop'
# CC0 plant/nature models (Poly Haven) plus ground/forest-floor PBR materials (ambientCG).
# Idempotent: existing asset folders are skipped; downloads are MD5-checked (Poly Haven) and zips are extracted only.
# Downloads are data. Nothing fetched is executed.
$taskRoot = Split-Path $PSScriptRoot -Parent
$phRoot = Join-Path $taskRoot 'ArtSource/PolyHaven'
$acRoot = Join-Path $taskRoot 'ArtSource/AmbientCG'
$docPath = Join-Path $taskRoot 'Docs/Assets.md'
$taskDate = '2026-10-09'
$capBytes = [long]3GB
$headers = @{'User-Agent'='TheWoodDevelopment/0.1 (local asset preparation)'}
$utf8 = New-Object Text.UTF8Encoding($false)
New-Item -ItemType Directory -Force -Path $phRoot,$acRoot | Out-Null
$script:bytes = [long]0
$script:models = 0
$script:textures = 0
$script:failed = @()
$imageExt = @('.png','.jpg','.jpeg','.exr','.tga')

function Get-SafePath($base,$rel) {
 $full = [IO.Path]::GetFullPath((Join-Path $base $rel))
 if (!$full.StartsWith(([IO.Path]::GetFullPath($base)+[IO.Path]::DirectorySeparatorChar),[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe asset-relative path' }
 return $full
}

function Get-VerifiedFile($url,$dest,$md5) {
 New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
 if ((Test-Path -LiteralPath $dest) -and ((Get-FileHash -LiteralPath $dest -Algorithm MD5).Hash -eq $md5)) { return }
 Invoke-WebRequest -Uri $url -OutFile ($dest+'.partial') -Headers $headers
 if ((Get-FileHash -LiteralPath ($dest+'.partial') -Algorithm MD5).Hash -ne $md5) { throw "Asset checksum failed: $dest" }
 Move-Item -LiteralPath ($dest+'.partial') -Destination $dest -Force
 $script:bytes += (Get-Item -LiteralPath $dest).Length
}

function Add-DocRow($key,$line) {
 $txt = [IO.File]::ReadAllText($docPath)
 if ($txt.Contains($key)) { return }
 if (!$txt.Contains('## CC0 plant and nature models (Fetch-CC0Plants.ps1)')) {
  $txt = $txt.TrimEnd() + "`n`n## CC0 plant and nature models (Fetch-CC0Plants.ps1)`n`n| asset | licence | date | files | main file sha256 |`n|---|---|---|---|---|`n"
  [IO.File]::WriteAllText($docPath, $txt, $utf8)
 }
 [IO.File]::AppendAllText($docPath, $line + "`n", $utf8)
}

# ---------- Poly Haven models ----------
$phCats = @('plants','trees','shrubs','flowers','grass','foliage','nature','rocks')
$phAssets = Invoke-RestMethod -Uri 'https://api.polyhaven.com/assets?t=models' -Headers $headers
$selected = @()
foreach ($p in $phAssets.PSObject.Properties) {
 $id = $p.Name; $meta = $p.Value
 if ($meta.PSObject.Properties.Name -contains 'license' -and $meta.license -and ($meta.license -notmatch 'CC0')) { Write-Warning "Skip $id licence $($meta.license)"; continue }
 $raw = $meta.categories
 $c = @()
 if ($raw) { if ($raw -is [array]) { $c = @($raw) } else { $c = @($raw.PSObject.Properties.Name) } }
 $c = @($c | ForEach-Object { ([string]$_).ToLowerInvariant() })
 $hit = $phCats | Where-Object { $c -contains $_ } | Select-Object -First 1
 if (!$hit) { continue }
 if (Test-Path -LiteralPath (Join-Path $phRoot $id)) { continue }
 $selected += [PSCustomObject]@{Id=$id;Rank=[array]::IndexOf($phCats,$hit);Rocks=($c -contains 'rocks')}
}
$selected = @($selected | Sort-Object Rank,Id)
Write-Output "Selected Poly Haven models: $($selected.Count)"
Write-Output (($selected | ForEach-Object { $_.Id }) -join ', ')

foreach ($sel in $selected) {
 if ($script:bytes -gt $capBytes) { Write-Warning 'Download cap 3 GB reached; stopping model fetch'; break }
 $id = $sel.Id
 try {
  $files = Invoke-RestMethod -Uri "https://api.polyhaven.com/files/$id" -Headers $headers
  $res = if ($sel.Rocks) {'2k'} else {'1k'}
  $model = $files.gltf.$res.gltf
  if (!$model -and $res -eq '2k') { $res = '1k'; $model = $files.gltf.'1k'.gltf }
  if (!$model) { throw "No gltf for $id" }
  $dir = Join-Path $phRoot $id
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $downloads = @([PSCustomObject]@{Relative="$id.gltf";File=$model})
  if ($model.include) { foreach ($prop in $model.include.PSObject.Properties) { $downloads += [PSCustomObject]@{Relative=$prop.Name;File=$prop.Value} } }
  foreach ($d in $downloads) {
   $dest = Get-SafePath $dir $d.Relative
   Get-VerifiedFile $d.File.url $dest $d.File.md5
   if ($d.Relative -like '*.gltf') { $script:models++ }
   elseif ($imageExt -contains ([IO.Path]::GetExtension($d.Relative)).ToLowerInvariant()) { $script:textures++ }
  }
  $mainPath = Join-Path $dir "$id.gltf"
  $sha = (Get-FileHash -LiteralPath $mainPath -Algorithm SHA256).Hash.ToLowerInvariant()
  Add-DocRow "https://polyhaven.com/a/$id)" "| [$id](https://polyhaven.com/a/$id) (CC0-1.0) | CC0-1.0 | $taskDate | PolyHaven/$id/ ($res, $($downloads.Count) files) | $sha |"
  Write-Output "Verified $id ($res)"
 } catch {
  $script:failed += $id
  Write-Warning "FAILED $id : $($_.Exception.Message)"
 }
}

# ---------- ambientCG materials ----------
$acWant = @('ground','forest','moss','bark','mud','snow','sand','gravel')
$acTarget = 15
$acGot = 0
$ac = Invoke-RestMethod -Uri 'https://ambientcg.com/api/v2/full_json?type=Material&include=tagData&limit=2000' -Headers $headers
$acList = @($ac.foundAssets | Where-Object {
 $_.assetId -and (-not (Test-Path -LiteralPath (Join-Path $acRoot $_.assetId))) -and
 ((((@($_.tags) -join ' ') + ' ' + [string]$_.title).ToLowerInvariant()) -match (($acWant | ForEach-Object { [regex]::Escape($_) }) -join '|'))
})
Write-Output "ambientCG candidates: $($acList.Count)"
foreach ($mat in $acList) {
 if ($acGot -ge $acTarget) { break }
 if ($script:bytes -gt $capBytes) { Write-Warning 'Download cap 3 GB reached; stopping material fetch'; break }
 $id = [string]$mat.assetId
 try {
  $zipDir = Join-Path ([IO.Path]::GetTempPath()) ("cc0-ambientcg-" + [guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force -Path $zipDir | Out-Null
  $zip = Join-Path $zipDir "$id`_1K-PNG.zip"
  Invoke-WebRequest -Uri "https://ambientcg.com/get?file=$id`_1K-PNG.zip" -OutFile $zip -Headers $headers
  $zipLen = (Get-Item -LiteralPath $zip).Length
  if ($zipLen -lt 10KB) { throw "zip too small ($zipLen bytes)" }
  $dest = Join-Path $acRoot $id
  New-Item -ItemType Directory -Force -Path $dest | Out-Null
  Expand-Archive -LiteralPath $zip -DestinationPath $dest -Force
  Remove-Item -LiteralPath $zipDir -Recurse -Force
  $script:bytes += $zipLen
  $imgs = @(Get-ChildItem -LiteralPath $dest -Recurse -File | Where-Object { $imageExt -contains $_.Extension.ToLowerInvariant() })
  $script:textures += $imgs.Count
  $main = $imgs | Where-Object { $_.Name -like '*_Color.png' } | Select-Object -First 1
  if (!$main) { $main = $imgs | Select-Object -First 1 }
  $sha = (Get-FileHash -LiteralPath $main.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  Add-DocRow "https://ambientcg.com/a/$id)" "| [$id](https://ambientcg.com/a/$id) (CC0-1.0) | CC0-1.0 | $taskDate | AmbientCG/$id/ (1K-PNG, $($imgs.Count) files; main $($main.Name)) | $sha |"
  $acGot++
  Write-Output "Extracted $id"
 } catch {
  $script:failed += $id
  Write-Warning "FAILED $id : $($_.Exception.Message)"
 }
}

$mb = [math]::Round($script:bytes / 1MB, 1)
Write-Output "Totals: models $($script:models), textures $($script:textures), ambientCG materials $acGot, MB $mb, failed $($script:failed.Count)"
if ($script:failed.Count) { Write-Output ("Failed: " + ($script:failed -join ', ')) }
Write-Output 'Powered by Poly Haven — https://polyhaven.com'
