#!/bin/bash
# Osprey Core Setup Wizard
# Run once when setting up a new instance.

echo "========================================="
echo "  OSPREY CORE — Setup Wizard"
echo "========================================="
echo ""

# Check OpenClaw
if ! command -v openclaw &> /dev/null; then
    echo "❌ OpenClaw not found. Install first: npm install -g openclaw"
    exit 1
fi

echo "✅ OpenClaw detected: $(openclaw --version 2>/dev/null || echo 'installed')"

# Who are you?
echo ""
read -p "Who is this instance for? (name): " OWNER
read -p "What's your domain? (cpa/service/developer/assistant): " DOMAIN

echo ""
echo "Configuring Osprey for $OWNER ($DOMAIN)..."
echo ""

# Create directories
mkdir -p ~/spark-vault/{memory,handoffs/inbox/real,projects,osprey}
mkdir -p ~/.hermes/secrets

# Copy core files
cp core/AGENTS.md ~/spark-vault/AGENTS.md
cp core/SOUL.md ~/spark-vault/SOUL.md

# Set up evidence loop
echo "Evidence loop files created in ~/spark-vault/osprey/"

# Secure secrets directory
chmod 700 ~/.hermes/secrets

echo ""
echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Add API keys to ~/.hermes/secrets/"
echo "  2. Run: openclaw gateway restart"
echo "  3. Your agent will wake up as the Bridge Officer"
echo ""
echo "Welcome to Osprey, $OWNER."
