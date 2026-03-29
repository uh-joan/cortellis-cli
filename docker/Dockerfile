# ==============================================================================
# Cortellis CLI — Browser Edition
# Layers Cortellis branding + CLI on top of HolyClaude
# ==============================================================================

FROM coderluii/holyclaude:slim

# ---------- Rebrand CloudCLI UI → Cortellis CLI ----------

ENV CLOUDCLI_DIST="/usr/local/lib/node_modules/@siteboon/claude-code-ui/dist"

# HTML title + manifest
RUN sed -i 's|<title>CloudCLI UI</title>|<title>Cortellis CLI</title>|g' "$CLOUDCLI_DIST/index.html"
RUN sed -i 's|"CloudCLI UI"|"Cortellis CLI"|g' "$CLOUDCLI_DIST/manifest.json" && \
    sed -i 's|CloudCLI UI web application|Cortellis Pharmaceutical Intelligence CLI|g' "$CLOUDCLI_DIST/manifest.json"

# JS bundle text replacements
RUN JS_FILE=$(ls $CLOUDCLI_DIST/assets/index-*.js) && \
    sed -i 's|"Welcome to Claude Code UI"|"Welcome to Cortellis CLI"|g' "$JS_FILE" && \
    sed -i 's|"Enter your credentials to access Claude Code UI"|"Enter your Cortellis CLI credentials"|g' "$JS_FILE" && \
    sed -i 's|"Sign in to your Claude Code UI account"|"Sign in to Cortellis CLI"|g' "$JS_FILE" && \
    sed -i 's|"Loading Claude Code UI"|"Loading Cortellis CLI"|g' "$JS_FILE" && \
    sed -i 's|"Claude Code UI"|"Cortellis CLI"|g' "$JS_FILE"

# Replace logos with transparent SVG + hide via CSS
COPY docker/branding/favicon.svg "$CLOUDCLI_DIST/favicon.svg"
RUN echo '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"/>' > "$CLOUDCLI_DIST/logo.svg" && \
    for f in "$CLOUDCLI_DIST"/logo-*.png; do printf '\x89PNG\r\n\x1a\n' > "$f" 2>/dev/null; done || true

# Inject ASCII banner + hide logo CSS
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
COPY docker/cortellis-claude.md /opt/cortellis-claude.md

# Entrypoint wrapper: appends Cortellis instructions to CLAUDE.md after HolyClaude bootstrap,
# and writes .env from container env vars
RUN cat > /opt/cortellis-init.sh <<'SCRIPT'
#!/bin/sh
# Append Cortellis instructions to CLAUDE.md (HolyClaude bootstrap may overwrite it)
if ! grep -q "Cortellis CLI" /home/claude/.claude/CLAUDE.md 2>/dev/null; then
  cat /opt/cortellis-claude.md >> /home/claude/.claude/CLAUDE.md
fi
# Write .env from env vars for python-dotenv
if [ -n "$CORTELLIS_USERNAME" ] && [ -n "$CORTELLIS_PASSWORD" ]; then
  echo "CORTELLIS_USERNAME=$CORTELLIS_USERNAME" > /opt/cortellis-cli/.env
  echo "CORTELLIS_PASSWORD=$CORTELLIS_PASSWORD" >> /opt/cortellis-cli/.env
fi
exec "$@"
SCRIPT
RUN chmod +x /opt/cortellis-init.sh

RUN chown -R claude:claude /home/claude/.claude /opt/cortellis-cli /opt/cortellis-venv

ENTRYPOINT ["/opt/cortellis-init.sh"]
CMD ["/init"]
