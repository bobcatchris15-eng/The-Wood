#!/usr/bin/env bash
# Runs every standalone core suite; exits non-zero if any fails.
cd "$(dirname "$0")/.." || exit 1
fail=0
run() { # run <name> <command...>: prints PASS/FAIL with wall seconds
  local name=$1; shift
  local t0=$(date +%s)
  "$@" >/dev/null 2>&1; local rc=$?
  local secs=$(( $(date +%s) - t0 ))
  if [ $rc -eq 0 ]; then echo "$name: PASS (${secs}s)"; else echo "$name: FAIL (${secs}s)"; fail=1; fi
}
run Core powershell -NoProfile -File Tools/Test-Core.ps1
for t in Hex Biomes Flora Discovery Streaming Atmosphere Soundscape Memory Save Entrance Overlay Ground Fauna Weather Landmarks; do
  run "$t" cmd //c "Tools\Test-$t.cmd"
done
exit $fail
