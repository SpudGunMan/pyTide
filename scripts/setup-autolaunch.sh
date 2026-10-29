#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="pytide"
INSTALL_DIR="/opt/pytide"
RUN_USER="${SUDO_USER:-${USER:-pi}}"
DISPLAY_ID=":0"

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
    --user)
      RUN_USER="$2"
      shift 2
      ;;
    --display)
      DISPLAY_ID="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: sudo bash scripts/setup-autolaunch.sh [--user pi] [--install-dir /opt/pytide] [--service-name pytide] [--display :0]" >&2
      exit 2
      ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Please run as root to install systemd units." >&2
  exit 1
fi

if ! id "${RUN_USER}" >/dev/null 2>&1; then
  echo "User '${RUN_USER}' does not exist." >&2
  exit 1
fi

TEMPLATE_PATH="${INSTALL_DIR}/pytide.service"
if [[ ! -f "${TEMPLATE_PATH}" ]]; then
  echo "Service template not found at ${TEMPLATE_PATH}" >&2
  exit 1
fi

RUN_HOME="$(getent passwd "${RUN_USER}" | cut -d: -f6)"
if [[ -z "${RUN_HOME}" ]]; then
  echo "Could not determine home directory for '${RUN_USER}'." >&2
  exit 1
fi

RUN_GROUP="$(id -gn "${RUN_USER}")"
if [[ -z "${RUN_GROUP}" ]]; then
  echo "Could not determine primary group for '${RUN_USER}'." >&2
  exit 1
fi

PYTHON_PATH="${INSTALL_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_PATH}" ]]; then
  PYTHON_PATH="/usr/bin/python3"
fi

XAUTH_PATH="${RUN_HOME}/.Xauthority"
TARGET_SERVICE="/etc/systemd/system/${SERVICE_NAME}.service"

sed \
  -e "s|__USER__|${RUN_USER}|g" \
  -e "s|__GROUP__|${RUN_GROUP}|g" \
  -e "s|__WORKDIR__|${INSTALL_DIR}|g" \
  -e "s|__PYTHON__|${PYTHON_PATH}|g" \
  -e "s|__DISPLAY__|${DISPLAY_ID}|g" \
  -e "s|__XAUTHORITY__|${XAUTH_PATH}|g" \
  "${TEMPLATE_PATH}" > "${TARGET_SERVICE}"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"

echo "Autolaunch installed: ${TARGET_SERVICE}"
echo "Check status with: systemctl status ${SERVICE_NAME}.service --no-pager"
echo "Tail logs with: journalctl -u ${SERVICE_NAME}.service -f"
