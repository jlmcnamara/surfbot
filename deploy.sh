#!/bin/bash
# Deploy SurfBot to Oracle VM
# Usage: ./deploy.sh

set -e

VM_HOST="146.235.196.92"
VM_USER="opc"
REMOTE_DIR="/home/opc/surfbot"

echo "🏄 Deploying SurfBot to $VM_HOST..."

# Sync files
rsync -avz --exclude '.git' --exclude 'venv' --exclude '__pycache__' --exclude '.env' \
    ./ ${VM_USER}@${VM_HOST}:${REMOTE_DIR}/

# Setup on remote
ssh ${VM_USER}@${VM_HOST} << 'ENDSSH'
cd /home/opc/surfbot

# Create venv if needed
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Install deps
source venv/bin/activate
pip install -r requirements.txt

# Install systemd service
sudo cp surfbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable surfbot
sudo systemctl restart surfbot

echo "✅ SurfBot deployed and running!"
sudo systemctl status surfbot --no-pager
ENDSSH
