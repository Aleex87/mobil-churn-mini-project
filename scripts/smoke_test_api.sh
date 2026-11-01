#!/usr/bin/env bash
#AI genererat
set -euo pipefail

IMAGE="${1:-churn-api:local}"
CONTAINER="churn-api-smoke-$$"
PORT=18000

# Always remove the test container, including when a check fails.
cleanup() {
    if [[ "$?" -ne 0 ]]; then
        docker logs "$CONTAINER" || true
    fi
    docker rm -f "$CONTAINER" > /dev/null 2>&1 || true
}
trap cleanup EXIT

docker run -d --name "$CONTAINER" \
    -p "127.0.0.1:$PORT:8000" "$IMAGE"

echo "[1/2] Waiting for the API..."

ready=false
for attempt in {1..30}; do
    if curl --fail --silent --max-time 2 \
        "http://127.0.0.1:$PORT/health" > /dev/null; then
        ready=true
        break
    fi
    sleep 1
done

if [[ "$ready" != "true" ]]; then
    echo "FAIL: API did not become ready"
    exit 1
fi

echo "PASS: /health responds"

echo "[2/2] Testing prediction..."

curl --fail --silent --show-error --max-time 10 \
    "http://127.0.0.1:$PORT/predict" \
    -H "Content-Type: application/json" \
    -d '{
        "alder": 35,
        "region": "Stockholm",
        "abonnemang": "Standard",
        "manader_som_kund": 12,
        "manadskostnad": 299.0,
        "data_gb_per_manad": 20.0,
        "supportarenden_12m": 2
    }' |
    docker exec -i "$CONTAINER" python -c '
import json
import sys

result = json.load(sys.stdin)
assert 0 <= result["churn_probability"] <= 1, "Invalid probability"
assert result["model_sha"], "Missing model version"
print("PASS: /predict returns a probability and model version")
'

echo "ALL API SMOKE TESTS PASSED"