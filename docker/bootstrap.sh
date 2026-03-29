#!/bin/bash
# ==============================================================================
# Cortellis CLI — Bootstrap script for HolyClaude container
# Runs once on container start to set up the CLI environment
# ==============================================================================

set -e

WORKSPACE="/workspace/cortellis-cli"
VENV="/workspace/.venv"
CLAUDE_DIR="/home/claude/.claude"

echo "[cortellis] Setting up Cortellis CLI..."

# 1. Create venv and install cortellis-cli
if [ ! -d "$VENV" ]; then
    echo "[cortellis] Creating virtual environment..."
    python3 -m venv "$VENV"
fi

echo "[cortellis] Installing cortellis-cli..."
"$VENV/bin/pip" install -q -e "$WORKSPACE"

# 2. Make cortellis available on PATH
ln -sf "$VENV/bin/cortellis" /usr/local/bin/cortellis

# 3. Write .env from container env vars (if set)
if [ -n "$CORTELLIS_USERNAME" ] && [ -n "$CORTELLIS_PASSWORD" ]; then
    echo "[cortellis] Configuring credentials..."
    cat > "$WORKSPACE/.env" <<EOF
CORTELLIS_USERNAME=$CORTELLIS_USERNAME
CORTELLIS_PASSWORD=$CORTELLIS_PASSWORD
EOF
fi

# 4. Set up Claude configuration
mkdir -p "$CLAUDE_DIR"

# Copy settings.json (if not already customized by user)
if [ ! -f "$CLAUDE_DIR/settings.json" ] || ! grep -q "cortellis" "$CLAUDE_DIR/settings.json" 2>/dev/null; then
    cp "$WORKSPACE/docker/settings.json" "$CLAUDE_DIR/settings.json"
    echo "[cortellis] Claude settings configured."
fi

# 5. Write CLAUDE.md so Claude knows about Cortellis
cat > "$CLAUDE_DIR/CLAUDE.md" <<'CLAUDEMD'
# Cortellis CLI

You have access to the Cortellis pharmaceutical intelligence CLI.
The virtual environment is already activated — `cortellis` is on PATH.

## How to use

Run commands directly:
```bash
cortellis --json drugs search --phase L --indication 238 --hits 10
```

Always use `--json` flag for parseable output. The working directory is `/workspace/cortellis-cli`.

## Important

- Indication, company, and country filters use numeric IDs
- Look up IDs first: `cortellis ontology search --term "obesity" --category indication`
- Action fields use text names, not IDs: `--action "glucagon"`
- Phase codes: L (Launched), C3 (Phase 3), C2 (Phase 2), C1 (Phase 1), DR (Discovery), DX (Discontinued)
- Multi-word values are auto-quoted in queries

## Available command groups

drugs, companies, deals, trials, regulations, conferences, literature, press-releases,
ontology, analytics, ner, targets, company-analytics, deals-intelligence, drug-design

Run `cortellis <group> --help` for full options.
CLAUDEMD

# 6. Copy SKILL.md to Claude's discoverable location
mkdir -p "$CLAUDE_DIR/skills"
cp "$WORKSPACE/cli_anything/cortellis/skills/SKILL.md" "$CLAUDE_DIR/skills/cortellis.md" 2>/dev/null || true

echo "[cortellis] Setup complete. Open http://localhost:3001 to start."
