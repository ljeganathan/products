#!/usr/bin/env pwsh
# Syncs this standalone StoreMate TN repo into the storemate-tn/ subfolder
# of the ljeganathan/products monorepo (which holds multiple products, one
# per top-level folder) and pushes the result.
#
# Requires a persistent local clone of the products repo - defaults to the
# sibling folder ../products relative to this repo; override with
# $env:PRODUCTS_CLONE_DIR if yours lives elsewhere.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StoremateDir = Resolve-Path (Join-Path $ScriptDir "..")
$ProductsDir = if ($env:PRODUCTS_CLONE_DIR) { $env:PRODUCTS_CLONE_DIR } else { Join-Path $StoremateDir "..\products" }

if (-not (Test-Path (Join-Path $ProductsDir ".git"))) {
    Write-Error "No products clone found at $ProductsDir`nClone it first: git clone https://github.com/ljeganathan/products.git `"$ProductsDir`""
    exit 1
}

Push-Location $ProductsDir
try {
    git pull origin main
    git subtree pull --prefix=storemate-tn "$StoremateDir" main -m "Sync StoreMate TN updates"
    git push origin main
} finally {
    Pop-Location
}
