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

# ── Force shells to use the bind-mounted SSH agent socket ────────────────────
# VS Code Dev Containers auto-injects its own SSH agent proxy socket via
# docker exec env at terminal start, overriding our devcontainer.json
# `containerEnv.SSH_AUTH_SOCK = /ssh-agent`. On this host that proxy is
# broken ("communication with agent failed"); the bind-mounted /ssh-agent
# (the host's actual agent) works. Force every shell to point at it.
echo ""
echo "→ Pinning SSH_AUTH_SOCK to the bind-mounted /ssh-agent socket..."
sudo tee /etc/profile.d/01-ssh-agent.sh > /dev/null <<'EOF'
# Override VS Code's auto-forward; /ssh-agent is the bind-mount from
# devcontainer.json that points at the host's working agent.
if [ -S /ssh-agent ]; then
    export SSH_AUTH_SOCK=/ssh-agent
fi
EOF
sudo chmod 0644 /etc/profile.d/01-ssh-agent.sh
# /etc/profile.d only covers login shells; cover interactive non-login too.
if ! grep -q "01-ssh-agent.sh" /etc/bash.bashrc 2>/dev/null; then
    echo '. /etc/profile.d/01-ssh-agent.sh' | sudo tee -a /etc/bash.bashrc > /dev/null
fi
echo "  ✓ override installed (will apply to new shells)"

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
