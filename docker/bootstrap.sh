#!/bin/bash
# ==============================================================================
# Cortellis CLI — Bootstrap script for HolyClaude container
# Runs on container start to install the CLI and configure Claude
# ==============================================================================

set -e

WORKSPACE="/workspace"
VENV="$WORKSPACE/.venv"
CLAUDE_DIR="/home/claude/.claude"
SKILLS_SRC="$WORKSPACE/cli_anything/cortellis/skills"

echo "[cortellis] Setting up Cortellis CLI..."

# ---------- 1. Virtual environment + install ----------

if [ ! -d "$VENV" ]; then
    echo "[cortellis] Creating virtual environment..."
    python3 -m venv "$VENV"
fi

echo "[cortellis] Installing cortellis-cli..."
"$VENV/bin/pip" install -q -e "$WORKSPACE"

# Make cortellis available on PATH
ln -sf "$VENV/bin/cortellis" /usr/local/bin/cortellis

# ---------- 2. Write .env from container env vars ----------

if [ -n "$CORTELLIS_USERNAME" ] && [ -n "$CORTELLIS_PASSWORD" ]; then
    echo "[cortellis] Configuring credentials..."
    cat > "$WORKSPACE/.env" <<EOF
CORTELLIS_USERNAME=$CORTELLIS_USERNAME
CORTELLIS_PASSWORD=$CORTELLIS_PASSWORD
EOF
fi

# ---------- 3. Copy SKILL.md to Claude's config ----------

mkdir -p "$CLAUDE_DIR/skills"

# Copy the main CLI skill reference
if [ -f "$SKILLS_SRC/cortellis-cli/SKILL.md" ]; then
    cp "$SKILLS_SRC/cortellis-cli/SKILL.md" "$CLAUDE_DIR/skills/cortellis-cli.md"
fi

# Copy all workflow skills (pipeline, landscape, drug-profile, etc.)
for skill_dir in "$SKILLS_SRC"/*/; do
    skill_name=$(basename "$skill_dir")
    if [ -f "$skill_dir/SKILL.md" ]; then
        cp "$skill_dir/SKILL.md" "$CLAUDE_DIR/skills/${skill_name}.md"
    fi
done

echo "[cortellis] Copied skills to $CLAUDE_DIR/skills/"

# ---------- 4. Write CLAUDE.md ----------

mkdir -p "$CLAUDE_DIR"
mkdir -p "$WORKSPACE/.claude"

cat > "$WORKSPACE/CLAUDE.md" <<'CLAUDEMD'
# Cortellis CLI

You have access to the Cortellis pharmaceutical intelligence CLI.
The `cortellis` command is on PATH — use it to answer ALL pharma/drug/trial/company questions.

**STRICT RULES — FOLLOW EXACTLY:**
1. **ONLY report data returned by the cortellis CLI.** Never supplement, guess, or add drugs/companies/trials from your training data.
2. **Give exact numbers from the data.** Never say "~8" or "6-7" — if the query returned 8 results, say "8".
3. **If data is missing from results, say so.** Do NOT fill gaps with your own knowledge.
4. **Never add drugs not in the results.** Only report what the CLI returned.
5. **Run the CLI for every question.** Do NOT answer pharma questions from memory. Always query first.
6. **NEVER truncate results.** Show ALL entries — never use "+ N others" or "and more".

## How to use

```bash
cortellis --json drugs search --phase L --indication 238 --hits 10
```

Always use `--json` flag for parseable output. The working directory is `/workspace`.

## Important

- Indication, company, and country filters use numeric IDs
- Look up IDs first: `cortellis ontology search --term "obesity" --category indication`
- Action fields use text names: `--action "glucagon"`
- Phase codes: L (Launched), C3 (Phase 3), C2 (Phase 2), C1 (Phase 1), DR (Discovery), DX (Discontinued)

## Available command groups

drugs, companies, deals, trials, regulations, conferences, literature, press-releases,
ontology, analytics, ner, targets, company-analytics, deals-intelligence, drug-design

Run `cortellis <group> --help` for full options.

## Workflow Skills

You have access to pharma workflow skills in ~/.claude/skills/:
- **cortellis-cli**: Full command reference (80+ subcommands)
- **pipeline**: Company pipeline analysis with CSV recipes
- **landscape**: Competitive landscape by indication
- **drug-profile**: Deep drug dossier with SWOT, financials, competitive context
- **deal-scout**: Deal intelligence and partnership analysis
- **target-map**: Target-drug-indication mapping
- **regulatory-watch**: Regulatory event tracking
- **patent-cliff**: Patent expiry and generic entry analysis

Read the relevant skill file before executing a workflow.
CLAUDEMD

# Also place in .claude/ for project-level discovery
cp "$WORKSPACE/CLAUDE.md" "$WORKSPACE/.claude/CLAUDE.md"

# Prepend to global CLAUDE.md if it exists and doesn't have Cortellis yet
if [ -f "$CLAUDE_DIR/CLAUDE.md" ]; then
    if ! head -5 "$CLAUDE_DIR/CLAUDE.md" | grep -q "Cortellis CLI"; then
        cat "$WORKSPACE/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md" > /tmp/claude-md-merged
        mv /tmp/claude-md-merged "$CLAUDE_DIR/CLAUDE.md"
    fi
else
    cp "$WORKSPACE/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
fi

# ---------- 5. Fix permissions ----------

chown -R claude:claude "$CLAUDE_DIR" 2>/dev/null || true

echo "[cortellis] Setup complete. Open http://localhost:3001 to start."
