#!/bin/bash
BACKEND_URL=${1:-"http://localhost:8000"}

echo "Resolvo Demo Alert Trigger"
echo "Backend: $BACKEND_URL"
echo ""

SCENARIO=${2:-"crashloop"}

case "$SCENARIO" in
  crashloop|a)
    echo "→ Triggering Scenario A: CrashLoop (NullPointerException from bad commit)"
    curl -s -X POST "$BACKEND_URL/api/v1/webhook/simulate/crashloop" \
      -H "Content-Type: application/json" | python3 -m json.tool
    ;;
  oom|b)
    echo "→ Triggering Scenario B: Memory OOM Kill"
    curl -s -X POST "$BACKEND_URL/api/v1/webhook/simulate/oom" \
      -H "Content-Type: application/json" | python3 -m json.tool
    ;;
  deadlock|c)
    echo "→ Triggering Scenario C: DB Deadlock (will escalate)"
    curl -s -X POST "$BACKEND_URL/api/v1/webhook/simulate/deadlock" \
      -H "Content-Type: application/json" | python3 -m json.tool
    ;;
  *)
    echo "Usage: $0 [backend_url] [crashloop|oom|deadlock]"
    echo ""
    echo "Examples:"
    echo "  $0                                    # trigger crashloop on localhost"
    echo "  $0 http://localhost:8000 oom          # trigger OOM scenario"
    echo "  $0 https://my-app.railway.app deadlock"
    exit 1
    ;;
esac

echo ""
echo "✅ Alert sent! Open http://localhost:5173 to watch Resolvo investigate."
