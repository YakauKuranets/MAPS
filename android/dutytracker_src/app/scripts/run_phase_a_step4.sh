#!/usr/bin/env bash
set -euo pipefail

# Deterministic runner for Android audit Phase A / Step 4.
# Runs commands strictly in order and stops on first failure.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -z "${JAVA_HOME:-}" ]]; then
  echo "[phase-a-step4] ERROR: JAVA_HOME is not set. Point it to JDK 17."
  exit 2
fi

if ! "$JAVA_HOME/bin/java" -version >/dev/null 2>&1; then
  echo "[phase-a-step4] ERROR: JAVA_HOME does not contain a usable java binary: $JAVA_HOME"
  exit 2
fi

echo "[phase-a-step4] Using JAVA_HOME=$JAVA_HOME"
echo "[phase-a-step4] 1/3 gradle :app:tasks"
gradle :app:tasks

echo "[phase-a-step4] 2/3 gradle :app:assembleDebug"
gradle :app:assembleDebug

echo "[phase-a-step4] 3/3 gradle :app:lintDebug"
gradle :app:lintDebug

echo "[phase-a-step4] SUCCESS: all Phase A / Step 4 commands passed."
