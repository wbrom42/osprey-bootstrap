#!/usr/bin/env bash
# Fleet Security Write — pushes ABOM and sweep findings to shared wiki
INSTANCE="${1:?instance required}"
ABOM="$HOME/spark-vault/security/abom.json"
SHARED="$HOME/spark-vault/wiki/fleet/security"
mkdir -p "$SHARED"

if [ -f "$ABOM" ]; then
    cp "$ABOM" "$SHARED/$(date +%Y-%m-%d)-${INSTANCE}-abom.json"
    echo "SECURITY: $INSTANCE ABOM → shared wiki"
fi
