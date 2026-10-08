$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskArtRoot = Join-Path $taskRoot 'ArtSource/PolyHaven'
New-Item -ItemType Directory -Force -Path $taskArtRoot | Out-Null
$taskHeaders = @{'User-Agent'='TheWoodDevelopment/0.1 (local asset preparation)'}
$taskRecords = @()
# Mature canopy and boulders complement the original undergrowth.
foreach ($taskId in @('pine_sapling_small','fern_02','grass_medium_01','grass_bermuda_01','grass_medium_02','rock_07','pine_tree_01','boulder_01','rock_moss_set_01','rock_moss_set_02')) {
 $taskFiles = Invoke-RestMethod -Uri "https://api.polyhaven.com/files/$taskId" -Headers $taskHeaders
 # Rocks use the 2k texture set so close-up surfaces stay sharp; all other assets stay 1k.
 $taskRes = if ($taskId -in @('rock_07','boulder_01','rock_moss_set_01','rock_moss_set_02')) {'2k'} else {'1k'}
 $taskModel = $taskFiles.gltf.$taskRes.gltf
 if (!$taskModel -and $taskRes -eq '2k') {
  Write-Warning "No 2k glTF for $taskId; falling back to 1k"
  $taskRes = '1k'
  $taskModel = $taskFiles.gltf.'1k'.gltf
 }
 if (!$taskModel) { throw "No $taskRes glTF for $taskId" }
 $taskDir = Join-Path $taskArtRoot $taskId
 New-Item -ItemType Directory -Force -Path $taskDir | Out-Null
 $taskDownloads = @([PSCustomObject]@{Relative="$taskId.gltf";File=$taskModel})
 foreach ($taskProperty in $taskModel.include.PSObject.Properties) {
  $taskDownloads += [PSCustomObject]@{Relative=$taskProperty.Name;File=$taskProperty.Value}
 }
 if ($taskId -eq 'pine_tree_01') {
  $taskDownloads += [PSCustomObject]@{Relative='textures/pine_tree_01_twig_alpha_1k.png';File=$taskFiles.twig_alpha.'1k'.png}
 }
 foreach ($taskDownload in $taskDownloads) {
  $taskDestination = [IO.Path]::GetFullPath((Join-Path $taskDir $taskDownload.Relative))
  if (!$taskDestination.StartsWith(([IO.Path]::GetFullPath($taskDir)+[IO.Path]::DirectorySeparatorChar),[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe asset-relative path' }
  New-Item -ItemType Directory -Force -Path (Split-Path $taskDestination -Parent) | Out-Null
  $taskValid = (Test-Path -LiteralPath $taskDestination) -and ((Get-FileHash -LiteralPath $taskDestination -Algorithm MD5).Hash -eq $taskDownload.File.md5)
  if (!$taskValid) {
   Invoke-WebRequest -Uri $taskDownload.File.url -OutFile ($taskDestination+'.partial') -Headers $taskHeaders
   if ((Get-FileHash -LiteralPath ($taskDestination+'.partial') -Algorithm MD5).Hash -ne $taskDownload.File.md5) { throw "Asset checksum failed: $taskDestination" }
   Move-Item -LiteralPath ($taskDestination+'.partial') -Destination $taskDestination -Force
  }
  $taskRecords += [PSCustomObject]@{Asset=$taskId;Source="https://polyhaven.com/a/$taskId";License='CC0-1.0';RelativePath="PolyHaven/$taskId/$($taskDownload.Relative)";Resolution=$taskRes;MD5=$taskDownload.File.md5}
 }
 Write-Output "Verified $taskId"
}
foreach ($taskId in @('forest_ground_04','forest_floor','withered_grass','gravel_ground_01')) {
 $taskFiles = Invoke-RestMethod -Uri "https://api.polyhaven.com/files/$taskId" -Headers $taskHeaders
 $taskDir = Join-Path $taskArtRoot $taskId
 New-Item -ItemType Directory -Force -Path $taskDir | Out-Null
 foreach ($taskMap in @('Diffuse','nor_dx','Rough')) {
  $taskFile = $taskFiles.$taskMap.'2k'.jpg
  $taskRelative = "$taskId-$taskMap.jpg"
  $taskDestination = Join-Path $taskDir $taskRelative
  if (!(Test-Path -LiteralPath $taskDestination) -or (Get-FileHash -LiteralPath $taskDestination -Algorithm MD5).Hash -ne $taskFile.md5) {
   Invoke-WebRequest -Uri $taskFile.url -OutFile ($taskDestination+'.partial') -Headers $taskHeaders
   if ((Get-FileHash -LiteralPath ($taskDestination+'.partial') -Algorithm MD5).Hash -ne $taskFile.md5) { throw "Texture checksum failed: $taskDestination" }
   Move-Item -LiteralPath ($taskDestination+'.partial') -Destination $taskDestination -Force
  }
  $taskRecords += [PSCustomObject]@{Asset=$taskId;Source="https://polyhaven.com/a/$taskId";License='CC0-1.0';RelativePath="PolyHaven/$taskId/$taskRelative";MD5=$taskFile.md5}
 }
 Write-Output "Verified textures $taskId"
}
$taskRecords | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 (Join-Path $taskRoot 'ArtSource/manifest.json')
Write-Output 'Powered by Poly Haven — https://polyhaven.com'

