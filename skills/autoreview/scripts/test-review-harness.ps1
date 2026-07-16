[CmdletBinding()]
param(
    [ValidateSet('malicious', 'benign')]
    [string] $Fixture,

    [ValidateSet('codex', 'claude', 'pi')]
    [string[]] $Engine,

    [Alias('h')]
    [switch] $Help
)

$ErrorActionPreference = 'Stop'

$Harness = Join-Path $PSScriptRoot 'test-review-harness.py'
$ScriptRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$CurrentRoot = (Get-Location).ProviderPath

function Get-CheckoutRoot([string] $Start) {
    $Current = [IO.Path]::GetFullPath($Start)
    while ($true) {
        if (Test-Path -LiteralPath (Join-Path $Current '.git')) {
            return $Current.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
        }
        $Parent = [IO.Directory]::GetParent($Current)
        if ($null -eq $Parent) { return $null }
        $Current = $Parent.FullName
    }
}

$CheckoutRoots = @(
    (Get-CheckoutRoot $CurrentRoot),
    (Get-CheckoutRoot $ScriptRoot)
) | Where-Object { $null -ne $_ } | Select-Object -Unique

function Test-ExternalApplication([string] $Path) {
    try {
        $Item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
        $ResolvedItem = if ($null -ne $Item.LinkType) {
            $Item.ResolveLinkTarget($true)
        }
        else {
            $Item
        }
        if ($null -eq $ResolvedItem) { return $false }
        $Resolved = $ResolvedItem.FullName
    }
    catch {
        return $false
    }
    foreach ($Root in $CheckoutRoots) {
        if ($Resolved -ieq $Root -or $Resolved.StartsWith($Root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            return $false
        }
    }
    return $true
}

function Get-ExternalApplications([string] $Name) {
    Get-Command $Name -CommandType Application -All -ErrorAction SilentlyContinue |
        Where-Object { Test-ExternalApplication $_.Source }
}

$ForwardedArgs = @()

if ($Help) {
    $ForwardedArgs += '--help'
}

if ($PSBoundParameters.ContainsKey('Fixture')) {
    $ForwardedArgs += @('--fixture', $Fixture)
}

if ($PSBoundParameters.ContainsKey('Engine')) {
    foreach ($SelectedEngine in $Engine) {
        $ForwardedArgs += @('--engine', $SelectedEngine)
    }
}

foreach ($PyLauncher in Get-ExternalApplications 'py') {
    & $PyLauncher.Source -3 -c 'import sys; raise SystemExit(sys.version_info < (3, 9))' *> $null
    if ($LASTEXITCODE -eq 0) {
        & $PyLauncher.Source -3 $Harness @ForwardedArgs
        exit $LASTEXITCODE
    }
}

foreach ($Python in Get-ExternalApplications 'python') {
    & $Python.Source -c 'import sys; raise SystemExit(sys.version_info < (3, 9))' *> $null
    if ($LASTEXITCODE -eq 0) {
        & $Python.Source $Harness @ForwardedArgs
        exit $LASTEXITCODE
    }
}

[Console]::Error.WriteLine('Python 3.9 or newer outside the reviewed checkout is required to run test-review-harness.')
exit 127
