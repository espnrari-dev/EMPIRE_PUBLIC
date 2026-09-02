#!/bin/bash
cd ~/EMPIRE_PUBLIC
mkdir -p logs
echo "EMPIRE_PUBLIC: No long‑running service to start." > logs/app.log
echo $$ > logs/app.pid
echo "EMPIRE_PUBLIC started (no service)"
