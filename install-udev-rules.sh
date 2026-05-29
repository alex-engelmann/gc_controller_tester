#!/bin/bash
# =============================================================================
# Mayflash GameCube Adapter udev Rules Installer
# =============================================================================
# Installs udev rules that allow non-root access to the Mayflash GameCube
# adapter (Wii U mode) and unbind the usbhid kernel driver so libusb can
# claim the device directly.
#
# Requirements:
#   - "51-gcadapter.rules" in the same directory as this script
#
# Usage:
#   chmod +x install-gcadapter-udev.sh
#   ./install-gcadapter-udev.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RULES_SRC="$SCRIPT_DIR/51-gcadapter.rules"
RULES_DST="/etc/udev/rules.d/51-gcadapter.rules"

if [ ! -f "$RULES_SRC" ]; then
    echo "ERROR: '51-gcadapter.rules' not found in $SCRIPT_DIR. Please place it alongside this script."
    exit 1
fi

echo "Installing GameCube adapter udev rules..."
sudo cp "$RULES_SRC" "$RULES_DST"
sudo udevadm control --reload-rules && sudo udevadm trigger
echo "Done. Unplug and replug your adapter, then run gc_gui_controller_tester.py or gc_cli_controller_tester.py."
