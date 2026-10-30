#!/usr/bin/env bash
set -euo pipefail

LIBTCD_VERSION="2.2.7-r3"
XTIDE_VERSION="2.16"
HARMONICS_ARCHIVE="harmonics-dwf-20251228-free"
HARMONICS_DIR="/usr/local/share/xtide"
XTIDE_PREFIX="/usr/local"
FORCE_BUILD="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --harmonics-dir)
      HARMONICS_DIR="$2"
      shift 2
      ;;
    --prefix)
      XTIDE_PREFIX="$2"
      shift 2
      ;;
    --force-build)
      FORCE_BUILD="1"
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: sudo bash scripts/install-xtide.sh [--harmonics-dir /usr/local/share/xtide] [--prefix /usr/local] [--force-build]" >&2
      exit 2
      ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Please run as root (for package install and /usr/local writes)." >&2
  exit 1
fi

TMP_DIR="$(mktemp -d /tmp/pytide-xtide-XXXXXX)"
cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

echo "Installing XTide build dependencies..."
apt-get update
apt-get install -y build-essential libpng-dev wget xz-utils

if [[ "${FORCE_BUILD}" != "1" ]] && command -v tide >/dev/null 2>&1; then
  echo "XTide binary already found at $(command -v tide); skipping rebuild."
else
  cd "${TMP_DIR}"

  echo "Building libtcd ${LIBTCD_VERSION}..."
  wget -q "https://flaterco.com/files/xtide/libtcd-${LIBTCD_VERSION}.tar.xz"
  tar xf "libtcd-${LIBTCD_VERSION}.tar.xz"
  cd "libtcd-${LIBTCD_VERSION%%-r*}"
  ./configure --prefix="${XTIDE_PREFIX}"
  make -j"$(nproc || echo 2)"
  make install
  ldconfig

  cd "${TMP_DIR}"
  echo "Building XTide ${XTIDE_VERSION}..."
  wget -q "https://flaterco.com/files/xtide/xtide-${XTIDE_VERSION}.tar.xz"
  tar xf "xtide-${XTIDE_VERSION}.tar.xz"
  cd "xtide-${XTIDE_VERSION}"
  ./configure --prefix="${XTIDE_PREFIX}" --without-x --disable-shared CPPFLAGS="-I${XTIDE_PREFIX}/include" LDFLAGS="-L${XTIDE_PREFIX}/lib"
  make -j"$(nproc || echo 2)"
  make install
fi

echo "Installing initial harmonics data..."
mkdir -p "${HARMONICS_DIR}"
cd "${TMP_DIR}"
wget -q "https://flaterco.com/files/xtide/${HARMONICS_ARCHIVE}.tar.xz"
tar xf "${HARMONICS_ARCHIVE}.tar.xz"

HARMONICS_STEM="${HARMONICS_ARCHIVE%-free}"
HARMONICS_TCD_SOURCE=""

for candidate in \
  "${HARMONICS_ARCHIVE}/${HARMONICS_ARCHIVE}.tcd" \
  "${HARMONICS_ARCHIVE}/${HARMONICS_STEM}-free.tcd" \
  "${HARMONICS_STEM}/${HARMONICS_ARCHIVE}.tcd" \
  "${HARMONICS_STEM}/${HARMONICS_STEM}-free.tcd"; do
  if [[ -f "${candidate}" ]]; then
    HARMONICS_TCD_SOURCE="${candidate}"
    break
  fi
done

if [[ -z "${HARMONICS_TCD_SOURCE}" ]]; then
  HARMONICS_TCD_SOURCE="$(find . -maxdepth 5 -type f -name '*.tcd' | head -n 1 || true)"
fi

if [[ -z "${HARMONICS_TCD_SOURCE}" ]]; then
  echo "Failed to locate harmonics .tcd file after extracting ${HARMONICS_ARCHIVE}.tar.xz" >&2
  exit 1
fi

cp -f "${HARMONICS_TCD_SOURCE}" "${HARMONICS_DIR}/"

echo "${HARMONICS_DIR}" > /etc/xtide.conf

echo "XTide setup complete."
echo "  tide binary: $(command -v tide || echo "not found in PATH")"
echo "  harmonics dir: ${HARMONICS_DIR}"
echo "  test command: ${XTIDE_PREFIX}/bin/tide -m l"
