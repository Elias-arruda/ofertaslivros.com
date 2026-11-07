#!/bin/sh
# Renderiza os HTML em PNG com o Chrome da máquina (sem dependência no projeto).
cd "$(dirname "$0")"
python3 gerar.py
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
for f in *.html; do
  case "$f" in *1920*) h=1920;; *) h=1350;; esac
  "$C" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --allow-file-access-from-files --virtual-time-budget=3000 \
    --window-size=1080,$h --screenshot="$PWD/${f%.html}.png" "file://$PWD/$f" 2>/dev/null
done
