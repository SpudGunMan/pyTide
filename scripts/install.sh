#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/pytide"
RUN_USER="${SUDO_USER:-${USER:-pi}}"
INSTALL_XTIDE="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --user)
      RUN_USER="$2"
      shift 2
      ;;
    --with-xtide)
      INSTALL_XTIDE="1"
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: sudo bash scripts/install.sh [--install-dir /opt/pytide] [--user pi] [--with-xtide]" >&2
      exit 2
      ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Please run as root (for apt and /opt writes)." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-venv python3-pip rsync build-essential libpng-dev wget xz-utils

echo "Deploying project to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
rsync -a --delete \
  --exclude ".git" \
  --exclude "__pycache__" \
  --exclude ".pytest_cache" \
  --exclude "settings.json" \
  "${REPO_DIR}/" "${INSTALL_DIR}/"

echo "Creating virtual environment..."
python3 -m venv "${INSTALL_DIR}/.venv"
"${INSTALL_DIR}/.venv/bin/pip" install --upgrade pip
"${INSTALL_DIR}/.venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"

if [[ ! -f "${INSTALL_DIR}/settings.json" ]]; then
  cp "${INSTALL_DIR}/settings.example.json" "${INSTALL_DIR}/settings.json"
fi

chown -R "${RUN_USER}:${RUN_USER}" "${INSTALL_DIR}"

if [[ "${INSTALL_XTIDE}" == "1" ]]; then
  echo "Running XTide + harmonics bootstrap..."
  bash "${INSTALL_DIR}/scripts/install-xtide.sh"
fi

echo "Install complete. Next step:"
echo "  sudo bash ${INSTALL_DIR}/scripts/setup-autolaunch.sh --user ${RUN_USER} --install-dir ${INSTALL_DIR}"
