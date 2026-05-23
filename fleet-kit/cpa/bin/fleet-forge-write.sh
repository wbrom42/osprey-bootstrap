#!/usr/bin/env bash
# Fleet Forge Write — pushes improvement cards to shared wiki
# Usage: fleet-forge-write.sh <instance> <card-file>
INSTANCE="${1:?instance required}"
CARD="${2:?card file required}"
SHARED="$HOME/spark-vault/wiki/fleet/forge"
mkdir -p "$SHARED"
DEST="$SHARED/$(date +%Y-%m-%d)-${INSTANCE}-$(basename "$CARD")"
cp "$CARD" "$DEST"
echo "FORGE: $INSTANCE → $DEST"
