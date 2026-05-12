#!/usr/bin/env bash
# Initialize the orchestrator scaffold inside a vault directory.
#
# Usage:
#     scripts/setup_vault.sh /path/to/vault
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <vault_root>" >&2
    exit 2
fi

VAULT="$1"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

mkdir -p "${VAULT}/.orchestrator"/{tasks,results,errors,logs,state}

if [[ ! -f "${VAULT}/CLAUDE.md" ]]; then
    cp "${REPO_ROOT}/templates/CLAUDE.md" "${VAULT}/CLAUDE.md"
    echo "Wrote ${VAULT}/CLAUDE.md (edit it to list your active projects)"
else
    echo "Skipped ${VAULT}/CLAUDE.md (already exists)"
fi

echo "Initialized ${VAULT}/.orchestrator/"
echo "Run: python -m orchestrator.cli status ${VAULT}"
