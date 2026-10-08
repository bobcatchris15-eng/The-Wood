#!/usr/bin/env bash
# Runs every standalone core suite; exits non-zero if any fails.
cd "$(dirname "$0")/.." || exit 1
fail=0
powershell -NoProfile -File Tools/Test-Core.ps1 >/dev/null 2>&1 && echo "Core: PASS" || { echo "Core: FAIL"; fail=1; }
for t in Hex Biomes Discovery Streaming Atmosphere Soundscape; do
  cmd //c "Tools\Test-$t.cmd" >/dev/null 2>&1 && echo "$t: PASS" || { echo "$t: FAIL"; fail=1; }
done
exit $fail
