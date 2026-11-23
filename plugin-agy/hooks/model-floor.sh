#!/bin/sh
# SessionStart hook: warn when the conversation runs on a tier that the four
# `model: inherit` review roles should not inherit. agy fires SessionStart for
# every conversation, subagents included (measured on agy 1.5.15, 2026-11-23),
# so the message tells a subagent to ignore it.
# ponytail: denylist of the two weak tiers seen so far (hydrogen, flash). Any
# other name, including "auto", passes silently; extend the list when a cheaper
# tier ships.
# The first "modelName" key wins. One inside lastUserInput cannot match: its
# quotes are escaped there.
model=$(grep -o '"modelName"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 |
  sed 's/^"modelName"[[:space:]]*:[[:space:]]*"//; s/"$//')
case "$(printf '%s' "$model" | tr '[:upper:]' '[:lower:]')" in
  *hydrogen*|*flash*)
    # Only the name is echoed into JSON: drop anything that could break the string.
    shown=$(printf '%s' "$model" | tr -cd 'A-Za-z0-9._/ ()-')
    printf '{"injectSteps":[{"systemMessage":{"systemMessage":"pilotfish: this conversation runs on %s. If you are the main agent: the four review and security roles inherit this model, so a reviewer is no stronger than the executor it checks. Say so whenever you report a review verdict, or ask the user to switch to a frontier model. If you are a subagent, ignore this message."}}]}\n' "$shown" ;;
  *) printf '{}\n' ;;
esac
