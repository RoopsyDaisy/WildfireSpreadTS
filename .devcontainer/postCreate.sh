#!/bin/bash
# postCreate.sh — runs once after the container is first built.
set -euo pipefail

# ── Python environment ────────────────────────────────────────────────────────
echo "→ Syncing Python environment..."
uv sync

# ── SSH agent check ───────────────────────────────────────────────────────────
echo ""
echo "→ Checking SSH agent forwarding..."

PASS=true

if [[ -z "${SSH_AUTH_SOCK:-}" ]]; then
    echo "  ✗ SSH_AUTH_SOCK is not set — agent forwarding is not configured."
    PASS=false
elif [[ ! -S "$SSH_AUTH_SOCK" ]]; then
    echo "  ✗ SSH_AUTH_SOCK=${SSH_AUTH_SOCK} is set but the socket does not exist."
    PASS=false
else
    IDENTITIES=$(ssh-add -l 2>&1 || true)
    if echo "$IDENTITIES" | grep -q "no identities"; then
        echo "  ✗ SSH agent socket found but no keys are loaded."
        PASS=false
    elif echo "$IDENTITIES" | grep -q "Could not open"; then
        echo "  ✗ SSH agent socket found but cannot be opened."
        PASS=false
    else
        echo "  ✓ SSH agent is forwarded and has keys loaded."
    fi
fi

if [[ "$PASS" == false ]]; then
    echo ""
    echo "  ┌─ How to fix SSH agent forwarding ──────────────────────────────────┐"
    echo "  │                                                                     │"
    echo "  │  On your LOCAL machine, add to ~/.ssh/config:                      │"
    echo "  │    Host <lab-host>                                                  │"
    echo "  │        ForwardAgent yes                                             │"
    echo "  │  And ensure your key is loaded into the local ssh-agent.           │"
    echo "  │  Rebuild the container after fixing.                                │"
    echo "  │                                                                     │"
    echo "  └─────────────────────────────────────────────────────────────────────┘"
    echo ""
fi

# ── Compatibility shim for hardcoded podman-style data paths ─────────────────
# Lorn's preprocessing scripts hardcode `/run/host/run/data_raid5/...` (podman
# mounts the host's /run under /run/host). In a devcontainer, /run/data_raid5
# is bind-mounted directly. Symlink so existing scripts work unmodified.
# TODO(BACKLOG): de-hardcode these paths in the scripts and remove the shim.
if [[ -d /run/data_raid5 && ! -e /run/host/run/data_raid5 ]]; then
    echo ""
    echo "→ Creating /run/host/run/data_raid5 → /run/data_raid5 compat symlink..."
    sudo mkdir -p /run/host/run
    sudo ln -sfn /run/data_raid5 /run/host/run/data_raid5
    echo "  ✓ symlink created"
fi

echo ""
echo "✓ postCreate complete."
