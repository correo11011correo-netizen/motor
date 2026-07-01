#!/bin/bash

# Evolution Ecosystem Startup Script
echo "🚀 Starting Evolution Ecosystem..."

# 1. Start the Evolution Motor (Slave) in the background
echo "Starting Evolution Motor on port 8000..."
export MOTOR_PORT=8000
python3 -m evolution.saas.main &
MOTOR_PID=$!

# 2. Start the Evolution Control Center (Master) in the foreground
echo "Starting Evolution Control Center on port 8001..."
export ADMIN_PORT=8001
python3 -m evolution.admin.server
# Note: The admin server should be configured to use ADMIN_PORT environment variable if supported, 
# or it defaults to 8001 as seen in its code.

# Ensure the motor is killed when the admin server stops
trap "kill $MOTOR_PID" EXIT
