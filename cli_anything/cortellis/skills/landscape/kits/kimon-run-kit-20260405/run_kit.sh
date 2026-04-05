#!/usr/bin/env bash
# run_kit.sh — Kimon run kit kimon-run-kit-20260405
# Run from repository root: bash cli_anything/cortellis/skills/landscape/kits/kimon-run-kit-20260405/run_kit.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Kit lives at: <repo>/cli_anything/cortellis/skills/landscape/kits/kimon-run-kit-20260405/
# So repo root is 6 levels up from the script directory
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../../.." && pwd)"
RECIPES="$REPO_ROOT/cli_anything/cortellis/skills/landscape/recipes"
KIT_DIR="$SCRIPT_DIR"
RAW="$REPO_ROOT/raw"

echo "=== Kimon run kit kimon-run-kit-20260405 ==="
echo "Repo root: $REPO_ROOT"
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

get_preset() {
  case "$1" in
    ipf) echo "respiratory" ;;
    als) echo "rare_cns" ;;
    *)   echo "default" ;;
  esac
}

get_name() {
  case "$1" in
    asthma)             echo "Asthma" ;;
    ipf)                echo "IPF" ;;
    als)                echo "ALS" ;;
    obesity)            echo "Obesity" ;;
    alzheimers-disease) echo "Alzheimer's Disease" ;;
    *)                  echo "$1" ;;
  esac
}

PRODUCED_FILES=()

for IND in asthma ipf als obesity alzheimers-disease; do
  IND_DIR="$RAW/$IND"
  if [ ! -d "$IND_DIR" ]; then
    echo "NOTE: $IND_DIR not found — skipping $IND"
    continue
  fi

  PRESET="$(get_preset "$IND")"
  NAME="$(get_name "$IND")"
  echo "--- $IND (preset: $PRESET) ---"

  python3 "$RECIPES/strategic_scoring.py" "$IND_DIR" "$PRESET" > "$IND_DIR/strategic_scores.md"
  echo "  strategic_scores.md OK"
  PRODUCED_FILES+=("$IND_DIR/strategic_scores.md")

  python3 "$RECIPES/opportunity_matrix.py" "$IND_DIR" > /dev/null 2>&1 || true
  if [ -f "$IND_DIR/opportunity_matrix.csv" ]; then
    echo "  opportunity_matrix.csv OK"
    PRODUCED_FILES+=("$IND_DIR/opportunity_matrix.csv")
  else
    echo "  opportunity_matrix.csv not produced"
  fi

  python3 "$RECIPES/strategic_narrative.py" "$IND_DIR" "$NAME" "$PRESET" > "$IND_DIR/strategic_briefing.md"
  echo "  strategic_briefing.md OK"
  PRODUCED_FILES+=("$IND_DIR/strategic_briefing.md")

  python3 "$RECIPES/scenario_library.py" "$IND_DIR" "$NAME" > "$IND_DIR/scenario_library.md"
  echo "  scenario_library.md OK"
  PRODUCED_FILES+=("$IND_DIR/scenario_library.md")

  echo ""
done

echo "--- Reproducibility tests ---"
python3 -m pytest "$REPO_ROOT/cli_anything/cortellis/tests/test_strategic_reproducibility.py" -v
echo ""

echo "--- Computing sha256 hashes ---"
HASH_FILE="$KIT_DIR/EXPECTED_HASHES.txt"
> "$HASH_FILE"
for F in "${PRODUCED_FILES[@]}"; do
  if [ -f "$F" ]; then
    shasum -a 256 "$F" >> "$HASH_FILE"
  fi
done
echo "Hashes written to $HASH_FILE ($(wc -l < "$HASH_FILE") files)"
echo ""

echo "=== Kit run complete. Exit 0. ==="
