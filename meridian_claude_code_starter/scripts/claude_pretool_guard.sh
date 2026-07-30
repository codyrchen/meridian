#!/usr/bin/env bash
set -euo pipefail
INPUT="$(cat)"
COMMAND="$(printf '%s' "$INPUT" | python -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))')"

if printf '%s' "$COMMAND" | grep -Eiq '(^|[;&| ])(rm -rf|git reset --hard|git push --force|drop[[:space:]]+database|truncate[[:space:]]+table)([ ;&|]|$)'; then
  echo "Blocked destructive command. Ask the user and use a safer, scoped alternative." >&2
  exit 2
fi

if printf '%s' "$COMMAND" | grep -Eiq '(BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|seed phrase|mnemonic)'; then
  echo "Blocked possible secret material in command." >&2
  exit 2
fi
exit 0
