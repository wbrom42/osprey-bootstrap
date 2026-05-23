#!/usr/bin/env bash
# Jekyll Behavioral Safety — Daily Test Run
# Runs all 6 test packs, reports results to stdout for cron delivery
set -e

echo "🧪 Jekyll Behavioral Safety — $(date -Imin)"
echo ""

PACKS=(
    "pack_isolation"
    "pack_b_lane_classification"
    "pack_c_domain_isolation"
    "pack_d_authority_laundering"
    "pack_e_acceptance_rate"
    "pack_f_shadow_swarm"
    "jh001_handoff_format"
    "jh002_har003_staleness"
    "jh003_cron_health"
    "jh004_supply_chain_integrity"
    "jh005_startup_context_integrity"
    "jh006_doctrine_staleness"
    "jh007_heartbeat_staleness"
    "pack_g_control_surface"
    "sulu_assertion_test"
)

PASS=0
FAIL=0
JEKYLL_DIR=~/spark-vault/projects/jekyll-agent

for pack in "${PACKS[@]}"; do
    if python3 "$JEKYLL_DIR/$pack.py" 2>/dev/null; then
        echo "  ✅ $pack"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $pack"
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "Results: $PASS pass, $FAIL fail"
if [ $FAIL -eq 0 ]; then
    echo "Health: GREEN"
else
    echo "Health: YELLOW — $FAIL test(s) failing"
fi
