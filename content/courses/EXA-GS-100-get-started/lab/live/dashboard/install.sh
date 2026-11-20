#!/usr/bin/env bash
# Deploy the New Year's Eve taxi dashboard to the kit's built-in Dash Server. See install.py for the detail.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 install.py "$@"
