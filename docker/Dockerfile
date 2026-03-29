# ==============================================================================
# Cortellis CLI — Browser Edition
# Layers Cortellis branding + CLI on top of HolyClaude
# ==============================================================================

FROM coderluii/holyclaude:slim

# ---------- Rebrand CloudCLI UI → Cortellis CLI ----------

# Path to CloudCLI dist
ENV CLOUDCLI_DIST="/usr/local/lib/node_modules/@siteboon/claude-code-ui/dist"

# Replace HTML title
RUN sed -i 's|<title>CloudCLI UI</title>|<title>Cortellis CLI</title>|g' "$CLOUDCLI_DIST/index.html"

# Replace manifest
RUN sed -i 's|"CloudCLI UI"|"Cortellis CLI"|g' "$CLOUDCLI_DIST/manifest.json" && \
    sed -i 's|CloudCLI UI web application|Cortellis Pharmaceutical Intelligence CLI|g' "$CLOUDCLI_DIST/manifest.json"

# Replace strings in the JS bundle
RUN JS_FILE=$(ls $CLOUDCLI_DIST/assets/index-*.js) && \
    sed -i 's|"Welcome to Claude Code UI"|"Welcome to Cortellis CLI"|g' "$JS_FILE" && \
    sed -i 's|"Enter your credentials to access Claude Code UI"|"Enter your Cortellis CLI credentials"|g' "$JS_FILE" && \
    sed -i 's|"Sign in to your Claude Code UI account"|"Sign in to Cortellis CLI"|g' "$JS_FILE" && \
    sed -i 's|"Loading Claude Code UI"|"Loading Cortellis CLI"|g' "$JS_FILE" && \
    sed -i 's|"Claude Code UI"|"Cortellis CLI"|g' "$JS_FILE"

# Copy custom favicon/logo
COPY docker/branding/favicon.svg "$CLOUDCLI_DIST/favicon.svg"

# Replace CloudCLI logos with transparent 1x1 pixel (banner replaces them)
RUN echo '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"/>' > "$CLOUDCLI_DIST/logo.svg" && \
    for f in "$CLOUDCLI_DIST"/logo-*.png; do printf '\x89PNG\r\n\x1a\n' > "$f" 2>/dev/null; done || true

# Inject banner script into index.html
COPY docker/branding/inject.js "$CLOUDCLI_DIST/cortellis-inject.js"
RUN sed -i 's|</head>|<script src="/cortellis-inject.js"></script></head>|' "$CLOUDCLI_DIST/index.html"

# ---------- Pre-install Cortellis CLI ----------

COPY . /opt/cortellis-cli

RUN python3 -m venv /opt/cortellis-venv && \
    /opt/cortellis-venv/bin/pip install -q -e /opt/cortellis-cli && \
    ln -sf /opt/cortellis-venv/bin/cortellis /usr/local/bin/cortellis

# ---------- Configure Claude for Cortellis ----------

COPY docker/settings.json /home/claude/.claude/settings.json
COPY cli_anything/cortellis/skills/SKILL.md /home/claude/.claude/skills/cortellis.md

# CLAUDE.md with Cortellis instructions
RUN mkdir -p /home/claude/.claude && \
    cat > /home/claude/.claude/CLAUDE.md <<'EOF'
# Cortellis CLI

You have access to the Cortellis pharmaceutical intelligence CLI.
The `cortellis` command is on PATH — no venv activation needed.

## How to use

Run commands directly:
```bash
cortellis --json drugs search --phase L --indication 238 --hits 10
```

Always use `--json` flag for parseable output.

## Important

- Indication, company, and country filters use numeric IDs
- Look up IDs first: `cortellis ontology search --term "obesity" --category indication`
- Action fields use text names: `--action "glucagon"`
- Phase codes: L (Launched), C3 (Phase 3), C2 (Phase 2), C1 (Phase 1), DR (Discovery), DX (Discontinued)

## Available command groups

drugs, companies, deals, trials, regulations, conferences, literature, press-releases,
ontology, analytics, ner, targets, company-analytics, deals-intelligence, drug-design

Run `cortellis <group> --help` for full options.
EOF

RUN chown -R claude:claude /home/claude/.claude /opt/cortellis-cli /opt/cortellis-venv
