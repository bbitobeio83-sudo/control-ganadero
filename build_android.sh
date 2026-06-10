#!/usr/bin/env bash
# ============================================================
# build_android.sh  —  Compila el APK de Control Ganadero
# Ejecutar desde WSL2 Ubuntu:  bash build_android.sh
# ============================================================
set -e

echo ""
echo "======================================================"
echo "  COMPILADOR APK — Control Ganadero"
echo "======================================================"

# ── 1. Dependencias del sistema ──────────────────────────────
echo ""
echo "[1/4] Instalando dependencias del sistema..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    git zip unzip \
    python3 python3-pip python3-venv \
    openjdk-17-jdk \
    build-essential \
    libssl-dev libffi-dev \
    libltdl-dev libjpeg-dev \
    autoconf automake libtool \
    ccache

# ── 2. Buildozer ────────────────────────────────────────────
echo ""
echo "[2/4] Instalando buildozer y python-for-android..."
pip3 install --quiet --upgrade buildozer python-for-android Cython==3.0.11

# ── 3. Variables de entorno Android ────────────────────────
export ANDROID_SDK_ROOT="$HOME/.buildozer/android/platform/android-sdk"
export ANDROID_NDK_HOME="$HOME/.buildozer/android/platform/android-ndk-r25b"
export PATH="$PATH:$ANDROID_SDK_ROOT/tools:$ANDROID_SDK_ROOT/platform-tools"

# ── 4. Compilar ──────────────────────────────────────────────
echo ""
echo "[3/4] Compilando APK (puede tomar 20-40 min la primera vez)..."
buildozer -v android debug

echo ""
echo "[4/4] Listo!"
APK=$(find bin/ -name "*.apk" 2>/dev/null | head -1)
if [ -n "$APK" ]; then
    echo "======================================================"
    echo "  APK generado: $APK"
    echo ""
    echo "  Para instalar en Android:"
    echo "  1. Copia el APK al teléfono"
    echo "  2. Activa 'Fuentes desconocidas' en Ajustes"
    echo "  3. Abre el APK desde el teléfono"
    echo "======================================================"
else
    echo "ADVERTENCIA: No se encontró el APK en bin/"
fi
