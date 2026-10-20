#!/usr/bin/env bash
# NR-IMS Codespace/DinD workaround.
# Docker 29+ uses nft backend, but stale iptables-legacy FORWARD DROP
# silently drops compose bridge traffic. This script sets legacy policy
# to ACCEPT. Idempotent, safe to run multiple times.
set -euo pipefail

if ! command -v iptables-legacy >/dev/null 2>&1; then
  echo "[fix_legacy_forward] iptables-legacy not installed — skipping"
  exit 0
fi

current="$(sudo iptables-legacy -S FORWARD 2>/dev/null | head -1 || true)"
echo "[fix_legacy_forward] current: ${current:-<none>}"

# iptables-legacy -S outputs "-P FORWARD DROP" (not "policy DROP")
if echo "$current" | grep -qE "^-P FORWARD DROP"; then
  echo "[fix_legacy_forward] legacy FORWARD DROP detected — fixing to ACCEPT"
  sudo iptables-legacy -P FORWARD ACCEPT
  echo "[fix_legacy_forward] FIXED"
else
  echo "[fix_legacy_forward] already OK — no change"
fi
