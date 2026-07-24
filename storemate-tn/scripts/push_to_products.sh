#!/usr/bin/env bash
# Syncs this standalone StoreMate TN repo into the storemate-tn/ subfolder
# of the ljeganathan/products monorepo (which holds multiple products, one
# per top-level folder) and pushes the result.
#
# Requires a persistent local clone of the products repo — defaults to the
# sibling folder ../products relative to this repo; override with
# PRODUCTS_CLONE_DIR if yours lives elsewhere.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STOREMATE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PRODUCTS_DIR="${PRODUCTS_CLONE_DIR:-$STOREMATE_DIR/../products}"

if [ ! -d "$PRODUCTS_DIR/.git" ]; then
  echo "No products clone found at $PRODUCTS_DIR" >&2
  echo "Clone it first: git clone https://github.com/ljeganathan/products.git \"$PRODUCTS_DIR\"" >&2
  exit 1
fi

cd "$PRODUCTS_DIR"
git pull origin main
git subtree pull --prefix=storemate-tn "$STOREMATE_DIR" main -m "Sync StoreMate TN updates"
git push origin main
