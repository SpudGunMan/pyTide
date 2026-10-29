#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="pytide"
INSTALL_DIR="/opt/pytide"
PURGE_INSTALL_DIR="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service-name)
      SERVICE_NAME="$2"
      shift 2
      ;;
    --install-dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --purge)
      PURGE_INSTALL_DIR="1"
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: sudo bash scripts/uninstall.sh [--service-name pytide] [--install-dir /opt/pytide] [--purge]" >&2
      exit 2
      ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Please run as root to uninstall systemd units." >&2
  exit 1
fi

SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

if systemctl list-unit-files | grep -q "^${SERVICE_NAME}\\.service"; then
  systemctl stop "${SERVICE_NAME}.service" || true
  systemctl disable "${SERVICE_NAME}.service" || true
fi

if [[ -f "${SERVICE_PATH}" ]]; then
  rm -f "${SERVICE_PATH}"
fi

systemctl daemon-reload
systemctl reset-failed || true

echo "Removed service: ${SERVICE_NAME}.service"

if [[ "${PURGE_INSTALL_DIR}" == "1" ]]; then
  if [[ -d "${INSTALL_DIR}" ]]; then
    rm -rf "${INSTALL_DIR}"
    echo "Removed install directory: ${INSTALL_DIR}"
  else
    echo "Install directory not found, skipped purge: ${INSTALL_DIR}"
  fi
else
  echo "Install directory retained: ${INSTALL_DIR}"
  echo "Use --purge to remove it as well."
fi

echo "Uninstall complete."
