#!/bin/bash
# Evidence Loop — Register → Verify → Score
# Run daily via cron. Checks registered predictions against current state.

PREDICTIONS_FILE="$HOME/spark-vault/projects/predictions/predictions.jsonl"
SCORES_FILE="$HOME/spark-vault/projects/predictions/scores.json"
VERIFICATIONS_FILE="$HOME/spark-vault/projects/predictions/verifications.jsonl"

echo "=== Evidence Loop $(date) ==="

# Register: count open predictions
OPEN=$(grep -c '"status":"OPEN"' "$PREDICTIONS_FILE" 2>/dev/null || echo 0)
echo "Open predictions: $OPEN"

# Verify: check for expired verifications
NOW=$(date -u +%s)
while IFS= read -r line; do
    verify_at=$(echo "$line" | python3 -c "import sys,json; print(json.loads(sys.stdin).get('verify_at',''))" 2>/dev/null)
    if [ -n "$verify_at" ]; then
        verify_ts=$(date -d "$verify_at" +%s 2>/dev/null || echo 0)
        if [ "$verify_ts" -lt "$NOW" ] 2>/dev/null; then
            echo "  ⏰ Due: $(echo "$line" | python3 -c "import sys,json; d=json.loads(sys.stdin); print(f'{d[\"prediction_id\"]} {d[\"asset\"]} {d[\"direction\"]}')" 2>/dev/null)"
        fi
    fi
done < "$PREDICTIONS_FILE"

echo "Done. View scores: cat $SCORES_FILE"
