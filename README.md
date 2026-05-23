# Osprey Bootstrap

System rebuild manual and fleet deployment kits for the Osprey agent infrastructure.

## What's Here

| Directory | Contents |
|-----------|----------|
| `docs/` | 14-stage system rebuild manual |
| `fleet-kit/` | Deployment packages for 4 fleet nodes (90 files each) |
| `bootstrap/` | Automated install + verify scripts |

## Quick Start

### Linux (DGX Spark)
```bash
git clone https://github.com/wbrom42/osprey-bootstrap.git
cd osprey-bootstrap
bash bootstrap/install.sh
bash bootstrap/verify.sh
```

### macOS (Apple Mini M4)
```bash
git clone https://github.com/wbrom42/osprey-bootstrap.git
cd osprey-bootstrap
bash bootstrap/install-macos.sh
bash bootstrap/verify-macos.sh
```

## Fleet Kit Contents (v1.2)

Every node receives the full Osprey DNA:

| Module | Files | Purpose |
|--------|-------|---------|
| `core/` | 8 | SOUL, AGENTS, HEARTBEAT, STARTUP_CONTEXT, Constitution, Operating Manual, MEMORY |
| `governance/` | 2 | AMFMP-001 (memory management), HBO (heartbeat operations) |
| `jekyll/` | 15 | 7 JH assertions + 8 Pack tests (including Pack H) |
| `trading/` | 42 | Full D-013 EC chain (thesis, adversarial review, calibration, veto, signals) |
| `security/` | 4 | ABOM template, credential sweep, phase-a doc |
| `forge/` | 6 | Gate runner, delegation, scope creep, symlink escape |
| `academy/` | 2 | Discovery template, radar reference |
| `bin/` | 7 | Setup, pulse, wiki, jekyll, security, forge, evidence-loop scripts |

## Nodes

| Node | Target Hardware | Status |
|------|----------------|--------|
| `service-manager` | Apple Mini M4 Pro | First deployment target |
| `cpa` | DGX Spark | Pipeline ready |
| `josh` | TBD | Pipeline ready |
| `austin` | TBD | Pipeline ready |

## Rebuild Manual

See `docs/system-rebuild-manual.md` — covers bare metal to fully operational in 14 stages, including emergency procedures, verification, and macOS appendix.
