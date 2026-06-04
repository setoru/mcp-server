@echo off
setlocal

rem ======== Edit these values ========
set "CONFIG_MERGE_DIR=C:\SWRDescriptionExports\vpcep-karpenter-06031141"
set "CONFIG_OUTPUT_FILE="
rem Leave CONFIG_OUTPUT_FILE empty to use:
rem   %CONFIG_MERGE_DIR%\restored\restored.bin
rem ==================================

set "SELF=%~f0"

if "%~1"=="" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$self = $env:SELF; $content = Get-Content -LiteralPath $self; $marker = ':__POWERSHELL__'; $index = [Array]::IndexOf($content, $marker); if ($index -lt 0) { throw 'Embedded PowerShell payload not found.' }; $script = ($content[($index + 1)..($content.Length - 1)] -join [Environment]::NewLine); & ([ScriptBlock]::Create($script))"
) else if "%~2"=="" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$self = $env:SELF; $content = Get-Content -LiteralPath $self; $marker = ':__POWERSHELL__'; $index = [Array]::IndexOf($content, $marker); if ($index -lt 0) { throw 'Embedded PowerShell payload not found.' }; $script = ($content[($index + 1)..($content.Length - 1)] -join [Environment]::NewLine); & ([ScriptBlock]::Create($script)) @args" -- "%~1"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$self = $env:SELF; $content = Get-Content -LiteralPath $self; $marker = ':__POWERSHELL__'; $index = [Array]::IndexOf($content, $marker); if ($index -lt 0) { throw 'Embedded PowerShell payload not found.' }; $script = ($content[($index + 1)..($content.Length - 1)] -join [Environment]::NewLine); & ([ScriptBlock]::Create($script)) @args" -- "%~1" "%~2"
)

set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
    echo SWR description restore finished.
) else (
    echo SWR description restore failed.
)
echo.
pause
exit /b %EXIT_CODE%

:__POWERSHELL__
param(
    [Parameter(Position = 0)]
    [string]$PartsDirectory,

    [Parameter(Position = 1)]
    [string]$OutputFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-Sha256Hex {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $stream = [System.IO.File]::OpenRead($Path)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()

    try {
        $hashBytes = $sha256.ComputeHash($stream)
        return ([System.BitConverter]::ToString($hashBytes) -replace "-", "")
    }
    finally {
        $sha256.Dispose()
        $stream.Dispose()
    }
}

if ([string]::IsNullOrWhiteSpace($PartsDirectory)) {
    $PartsDirectory = $env:CONFIG_MERGE_DIR
}

if ([string]::IsNullOrWhiteSpace($PartsDirectory)) {
    throw "Parts directory is required. Edit CONFIG_MERGE_DIR at the top of restore-swr-desc.cmd, or pass it as the first argument."
}

$PartsDirectory = [System.IO.Path]::GetFullPath($PartsDirectory.Trim('"'))
if (-not (Test-Path -LiteralPath $PartsDirectory)) {
    throw "Parts directory not found: $PartsDirectory"
}

$partsDirectoryItem = Get-Item -LiteralPath $PartsDirectory
if (-not $partsDirectoryItem.PSIsContainer) {
    throw "PartsDirectory must be a directory."
}

$manifest = $null
$manifestPath = Join-Path $partsDirectoryItem.FullName "manifest.json"
if (Test-Path -LiteralPath $manifestPath) {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
}

$partPattern = "description.part*.txt"

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = $env:CONFIG_OUTPUT_FILE
}

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $restoreDirectory = Join-Path $partsDirectoryItem.FullName "restored"

    if ($manifest -and $manifest.OriginalFileName) {
        $restoreFileName = [string]$manifest.OriginalFileName
    }
    else {
        $restoreFileName = "restored.bin"
    }

    $OutputFile = Join-Path $restoreDirectory $restoreFileName
}

$outputFullPath = [System.IO.Path]::GetFullPath($OutputFile.Trim('"'))
$outputParent = Split-Path -Path $outputFullPath -Parent
if ($outputParent -and -not (Test-Path -LiteralPath $outputParent)) {
    New-Item -ItemType Directory -Path $outputParent -Force | Out-Null
}

$partInfos = @(
    Get-ChildItem -LiteralPath $partsDirectoryItem.FullName -File -Filter $partPattern |
        ForEach-Object {
            $match = [regex]::Match($_.Name, "\.part(\d+)\.[^.]+$", "IgnoreCase")
            $partNumber = $null

            if ($match.Success) {
                $partNumber = [int]$match.Groups[1].Value
            }

            [pscustomobject]@{
                File = $_
                PartNumber = $partNumber
            }
        }
)

if ($partInfos.Count -eq 0) {
    throw "No part files were found in $($partsDirectoryItem.FullName) using pattern $partPattern"
}

$numberedParts = @($partInfos | Where-Object { $null -ne $_.PartNumber })

if ($numberedParts.Count -eq $partInfos.Count) {
    $duplicatePartNumbers = @(
        $numberedParts |
            Group-Object -Property PartNumber |
            Where-Object { $_.Count -gt 1 }
    )

    if ($duplicatePartNumbers.Count -gt 0) {
        throw "Duplicate part number found: $($duplicatePartNumbers[0].Name)"
    }

    $orderedParts = @($partInfos | Sort-Object -Property PartNumber)

    for ($index = 0; $index -lt $orderedParts.Count; $index++) {
        $expectedPartNumber = $index + 1
        if ($orderedParts[$index].PartNumber -ne $expectedPartNumber) {
            throw "Missing part file. Expected part number $expectedPartNumber, found $($orderedParts[$index].PartNumber)."
        }
    }
}
else {
    $orderedParts = @($partInfos | Sort-Object -Property @{ Expression = { $_.File.Name } })
}

if ($manifest -and $manifest.PartCount -and ([int]$manifest.PartCount -ne $orderedParts.Count)) {
    throw "Part count does not match manifest. Expected $($manifest.PartCount), found $($orderedParts.Count)."
}

$tempFilePath = [System.IO.Path]::GetTempFileName()
$writer = $null
$totalBase64Length = 0

try {
    if (Test-Path -LiteralPath $outputFullPath) {
        Remove-Item -LiteralPath $outputFullPath -Force
    }

    $writer = [System.IO.StreamWriter]::new($tempFilePath, $false, [System.Text.Encoding]::ASCII)
    $writer.WriteLine("-----BEGIN CERTIFICATE-----")

    $carry = ""

    foreach ($part in $orderedParts) {
        $content = Get-Content -LiteralPath $part.File.FullName -Raw
        if ($null -eq $content) {
            $content = ""
        }

        $content = [regex]::Replace($content, "\s+", "")

        if ($content.Length -eq 0) {
            throw "Part file is empty: $($part.File.FullName)"
        }

        if ($content -match "[^A-Za-z0-9+/=]") {
            throw "Part file contains characters that are not valid Base64: $($part.File.FullName)"
        }

        $totalBase64Length += $content.Length
        $data = $carry + $content
        $offset = 0

        while (($data.Length - $offset) -ge 64) {
            $writer.WriteLine($data.Substring($offset, 64))
            $offset += 64
        }

        if ($offset -lt $data.Length) {
            $carry = $data.Substring($offset)
        }
        else {
            $carry = ""
        }
    }

    if (($totalBase64Length % 4) -ne 0) {
        throw "Combined Base64 length is not divisible by 4. A part file may be missing or damaged."
    }

    if ($carry.Length -gt 0) {
        $writer.WriteLine($carry)
    }

    $writer.WriteLine("-----END CERTIFICATE-----")
    $writer.Dispose()
    $writer = $null

    $certutilOutput = & certutil.exe -f -decode $tempFilePath $outputFullPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "certutil failed: $($certutilOutput -join [Environment]::NewLine)"
    }

    if ($manifest -and $manifest.Sha256) {
        $actualHash = Get-Sha256Hex -Path $outputFullPath
        if ($actualHash -ne [string]$manifest.Sha256) {
            throw "Restored file hash does not match manifest. Expected $($manifest.Sha256), got $actualHash."
        }

        Write-Host "SHA256 verified: $actualHash"
    }

    Write-Host "Parts directory: $($partsDirectoryItem.FullName)"
    Write-Host "Output file: $outputFullPath"
    Write-Host "Parts restored: $($orderedParts.Count)"
    Write-Host "Base64 characters: $totalBase64Length"
}
finally {
    if ($null -ne $writer) {
        $writer.Dispose()
    }

    Remove-Item -LiteralPath $tempFilePath -Force -ErrorAction SilentlyContinue
}
