#!/bin/sh
# Read-only host prerequisite report. No env files, passwords, or credentials.
set -u
printf '%s\n' '[OS]'
cat /etc/os-release
printf '%s\n' '[CPU architecture / kernel]'
uname -m
uname -r
printf '%s\n' '[GPU / driver]'
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=index,name,driver_version --format=csv
    nvidia-smi -L
else
    printf '%s\n' 'nvidia-smi: not installed or not on PATH'
fi
printf '%s\n' '[Container tools]'
if command -v docker >/dev/null 2>&1; then
    docker version --format '{{.Client.Version}} / {{.Server.Version}}'
    docker compose version
else
    printf '%s\n' 'docker: not installed or not on PATH'
fi
if command -v nvidia-ctk >/dev/null 2>&1; then
    nvidia-ctk --version
else
    printf '%s\n' 'nvidia-ctk: not installed or not on PATH'
fi
printf '%s\n' '[Python]'
python3 --version
