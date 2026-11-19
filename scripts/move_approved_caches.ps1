$UserLocal = [Environment]::GetFolderPath('LocalApplicationData')
$PipCache = Join-Path $UserLocal 'pip\cache'
$UvCache = Join-Path $UserLocal 'uv\cache'
. "$PSScriptRoot\environment.ps1"

$Transfers = @(
    @{Source=$PipCache; Destination=(Join-Path $ProjectRoot 'disk_kurtarma\2026-11-18\pip_cache')},
    @{Source=$UvCache; Destination=(Join-Path $ProjectRoot 'disk_kurtarma\2026-11-18\uv_cache')}
)
$ReportRoot = Join-Path $ProjectRoot 'results\disk_transfer'
New-Item -ItemType Directory -Force -Path $ReportRoot | Out-Null
$Reports = @()
$Before = [IO.DriveInfo]::new('C:\').AvailableFreeSpace

foreach ($Transfer in $Transfers) {
    $Source = [IO.Path]::GetFullPath($Transfer.Source).TrimEnd('\')
    $Destination = [IO.Path]::GetFullPath($Transfer.Destination).TrimEnd('\')
    $ApprovedSources = @($PipCache, $UvCache)
    if ($Source -notin $ApprovedSources) { throw 'Source is outside the two approved caches.' }
    if (-not $Destination.StartsWith($ProjectRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Destination is outside the D project.'
    }
    if (-not (Test-Path -LiteralPath $Source)) { continue }
    $RootItem = Get-Item -LiteralPath $Source -Force
    if ($RootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Cache root is a reparse point.' }
    $Items = @(Get-ChildItem -LiteralPath $Source -Recurse -Force -ErrorAction Stop)
    if (@($Items | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count -gt 0) {
        throw 'A cache contains a link. Inspect it before moving.'
    }
    $Files = @($Items | Where-Object { -not $_.PSIsContainer })
    $Records = @()
    $Count = 0
    foreach ($File in $Files) {
        $Absolute = [IO.Path]::GetFullPath($File.FullName)
        if (-not $Absolute.StartsWith($Source + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'File path escaped the approved cache.'
        }
        $Relative = $Absolute.Substring($Source.Length + 1)
        $Target = Join-Path $Destination $Relative
        New-Item -ItemType Directory -Force -Path ([IO.Path]::GetDirectoryName($Target)) | Out-Null
        $SourceHash = (Get-FileHash -LiteralPath $Absolute -Algorithm SHA256 -ErrorAction Stop).Hash
        if (Test-Path -LiteralPath $Target) {
            if ((Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash -ne $SourceHash) {
                throw ('Existing destination differs: ' + $Target)
            }
        } else {
            Copy-Item -LiteralPath $Absolute -Destination $Target -ErrorAction Stop
        }
        if ((Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash -ne $SourceHash) {
            throw ('Copy verification failed: ' + $Relative)
        }
        $Records += [PSCustomObject]@{RelativePath=$Relative; Bytes=$File.Length; SHA256=$SourceHash; Removed=$false}
        $Count++
        if ($Count % 250 -eq 0) { Write-Output ("Verified $Count / $($Files.Count) files in $Source") }
    }

    # Deletion starts only after the complete cache snapshot has a verified D copy.
    foreach ($Record in $Records) {
        $Original = [IO.Path]::GetFullPath((Join-Path $Source $Record.RelativePath))
        if (-not $Original.StartsWith($Source + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Deletion target escaped the approved cache.'
        }
        if (Test-Path -LiteralPath $Original) {
            if ((Get-FileHash -LiteralPath $Original -Algorithm SHA256).Hash -ne $Record.SHA256) {
                throw ('Source changed after copying; source retained: ' + $Record.RelativePath)
            }
            Remove-Item -LiteralPath $Original -Force -ErrorAction Stop
            $Record.Removed = $true
        }
    }
    # Remove only empty child directories. Concurrently created files are retained.
    foreach ($Directory in @($Items | Where-Object PSIsContainer | Sort-Object { $_.FullName.Length } -Descending)) {
        $Path = [IO.Path]::GetFullPath($Directory.FullName)
        if (-not $Path.StartsWith($Source + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Directory escaped approved cache.' }
        if ((Test-Path -LiteralPath $Path) -and @(Get-ChildItem -LiteralPath $Path -Force).Count -eq 0) {
            Remove-Item -LiteralPath $Path -Force -ErrorAction Stop
        }
    }
    $Report = [PSCustomObject]@{
        Source=$Source; Destination=$Destination; Files=$Records.Count
        VerifiedBytes=($Records | Measure-Object Bytes -Sum).Sum
        RemovedFiles=@($Records | Where-Object Removed).Count
        Entries=$Records
    }
    $Reports += $Report
    $Report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $ReportRoot ((Split-Path $Destination -Leaf) + '.json')) -Encoding UTF8
    Write-Output ("Completed $Source, verified files: $($Records.Count), removed originals: $($Report.RemovedFiles)")
}
$After = [IO.DriveInfo]::new('C:\').AvailableFreeSpace
[PSCustomObject]@{
    CFreeBeforeGiB=[math]::Round($Before/1GB,3)
    CFreeAfterGiB=[math]::Round($After/1GB,3)
    NetFreeChangeMiB=[math]::Round(($After-$Before)/1MB,1)
    VerifiedTransferredMiB=[math]::Round(($Reports | Measure-Object VerifiedBytes -Sum).Sum/1MB,1)
} | ConvertTo-Json | Tee-Object -FilePath (Join-Path $ReportRoot 'summary.json')
