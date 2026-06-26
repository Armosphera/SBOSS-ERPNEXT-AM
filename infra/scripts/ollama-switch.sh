#!/usr/bin/env bash
# ollama-switch.sh — switch the active Ollama model for frappe_ai_local.
# Usage: bash infra/scripts/ollama-switch.sh <model-tag>
# Example: bash infra/scripts/ollama-switch.sh gemma2:2b
#
# Reads current default from common_site_config.json (key: ollama_default_model),
# updates it via `bench set-config`, then prints both the old and new value so
# the user can see what changed. Does NOT restart any container — the Ollama
# client picks up the new value on its next call.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <model-tag>"
    echo "Available (currently pulled in dev stack):"
    echo "  gemma4:e2b   (Gemma 4 Effective 2B, Q4_K_M, 7.2 GB - higher quality)"
    echo "  gemma2:2b    (Gemma 2 2B, Q4_0, 1.6 GB - faster, smaller)"
    echo ""
    echo "Current default:"
    docker exec compose-bench-1 bash -c \
        "cd /workspace/frappe-bench && bench --site all show-config ollama_default_model 2>/dev/null \
         || echo '(not set — defaults to gemma4:e2b)'"
    exit 2
fi

NEW_MODEL="$1"

# Verify the model is actually pulled in ollama.
if ! docker exec compose-ollama-1 ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "$NEW_MODEL"; then
    echo "ERROR: model '$NEW_MODEL' is not pulled in compose-ollama-1."
    echo "Pulled models:"
    docker exec compose-ollama-1 ollama list
    echo ""
    echo "To pull it: docker exec compose-ollama-1 ollama pull $NEW_MODEL"
    exit 1
fi

# Read old value (best-effort).
OLD_MODEL=$(docker exec compose-bench-1 cat /workspace/frappe-bench/sites/common_site_config.json 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("ollama_default_model","(unset — defaults to gemma4:e2b)"))' \
    2>/dev/null || echo "(unset — defaults to gemma4:e2b)")

# Update via bench.
docker exec compose-bench-1 bash -c \
    "cd /workspace/frappe-bench && bench set-config -g ollama_default_model $NEW_MODEL" >/dev/null

echo "OK: ollama_default_model: $OLD_MODEL -> $NEW_MODEL"
echo ""
echo "The frappe_ai_local Ollama client will pick up the new value on its next call."
echo "No container restart needed."
echo ""
echo "Verify the model is reachable:"
echo "  docker exec compose-ollama-1 ollama run $NEW_MODEL 'Say Barev in one word'"