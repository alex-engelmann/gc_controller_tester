#!/usr/bin/env python3
"""
gc-controller-tester-cli
A command line tester for the Mayflash GameCube adapter (Wii U mode).
"""
import sys
import usb.core
import usb.util

# =========================================
# CONSTANTS
# =========================================

# USB vendor and product IDs for the Mayflash adapter in Wii U mode.
# In PC mode the adapter presents different IDs and won't be found here.
VENDOR_ID  = 0x057e  # Nintendo
PRODUCT_ID = 0x0337  # Wii U GameCube Adapter

# Analog stick and trigger calibration.
# DEADZONE: how far a stick must move from center before registering.
# REST_L/R: the raw byte value of each trigger at rest (unpressed).
# These were determined empirically from raw USB packet data.
DEADZONE = 5
REST_L   = 0x22
REST_R   = 0x25

VERSION = "1.0.0"

# =========================================
# USB SETUP
# =========================================

def init_adapter():
    # Search for the adapter by vendor and product ID
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

    if dev is None:
        print("Error: GameCube adapter not found.")
        print("Make sure the Mayflash adapter is connected and in Wii U mode.")
        sys.exit(1)

    try:
        dev.set_configuration()
        # Send the adapter's init command. This is required to activate
        # controller polling — without it the adapter sends no data.
        dev.write(0x02, b'\x13')
    except usb.core.USBError as e:
        print(f"Error: Could not open adapter: {e}")
        print("Try running the udev setup script and replugging the adapter.")
        sys.exit(1)

    return dev

# =========================================
# DECODING
# =========================================

def apply_deadzone(value, center):
    # Returns the offset from center, or 0 if within the deadzone threshold.
    # This prevents idle stick noise from registering as movement.
    offset = value - center
    return 0 if abs(offset) < DEADZONE else offset


def decode(data):
    # The adapter sends 37-byte packets covering all 4 controller ports.
    # Byte 1 is the status byte for port 1. Bit 4 indicates a controller
    # is connected — if not set, skip this packet.
    if not (data[1] & 0x10):
        return None

    # Button states are packed as individual bits across two bytes.
    # Each bitmask isolates one button from the byte.
    b1 = data[2]  # A, B, X, Y, D-pad
    b2 = data[3]  # Start, Z, R, L

    buttons = {
        'A':       bool(b1 & 0x01),
        'B':       bool(b1 & 0x02),
        'X':       bool(b1 & 0x04),
        'Y':       bool(b1 & 0x08),
        'D-Left':  bool(b1 & 0x10),
        'D-Right': bool(b1 & 0x20),
        'D-Down':  bool(b1 & 0x40),
        'D-Up':    bool(b1 & 0x80),
        'Start':   bool(b2 & 0x01),
        'Z':       bool(b2 & 0x02),
        'R':       bool(b2 & 0x04),  # R digital click (full press)
        'L':       bool(b2 & 0x08),  # L digital click (full press)
    }

    # Analog axes are single bytes. Center values were determined empirically.
    # Triggers are offset by their rest value and deadzone so they read 0
    # at rest and increase as the trigger is pressed.
    axes = {
        'Main X': apply_deadzone(data[4], 0x80),
        'Main Y': apply_deadzone(data[5], 0x85),
        'C X':    apply_deadzone(data[6], 0x80),
        'C Y':    apply_deadzone(data[7], 0x83),
        'L Trig': max(0, data[8] - REST_L - DEADZONE),
        'R Trig': max(0, data[9] - REST_R - DEADZONE),
    }

    return buttons, axes

# =========================================
# FORMATTING
# =========================================

def format_buttons(buttons):
    # Return only the names of currently pressed buttons
    pressed = [name for name, val in buttons.items() if val]
    if not pressed:
        return "none"
    return "  ".join(pressed)


def format_axes(axes):
    # Return only axes with non-zero values, with explicit +/- sign
    active = {k: v for k, v in axes.items() if v != 0}
    if not active:
        return "center"
    return "  ".join(f"{k}: {v:+d}" for k, v in active.items())


def print_header():
    print()
    print("  gc-controller-tester CLI  v" + VERSION)
    print("  ─────────────────────────────────────")
    print("  Adapter : Mayflash 4-port (Wii U mode)")
    print("  Device  : 057e:0337")
    print("  Port    : 1")
    print("  ─────────────────────────────────────")
    print("  Press Ctrl+C to exit.")
    print()

# =========================================
# MAIN LOOP
# =========================================

def main():
    dev = init_adapter()
    print_header()

    prev_buttons = None
    prev_axes    = None

    try:
        while True:
            try:
                # Read one 37-byte packet from the adapter's IN endpoint.
                # Timeout of 5000ms before retrying.
                data = dev.read(0x81, 37, timeout=5000)
            except usb.core.USBTimeoutError:
                continue

            result = decode(data)
            if not result:
                continue

            buttons, axes = result

            # Only print when state changes to avoid flooding the terminal
            if buttons != prev_buttons:
                print(f"  BTN  {format_buttons(buttons)}")
                prev_buttons = buttons

            if axes != prev_axes:
                print(f"  AXIS {format_axes(axes)}")
                prev_axes = axes

    except KeyboardInterrupt:
        print("\n  Stopped.")
        sys.exit(0)

    except usb.core.USBError as e:
        print(f"\n  USB error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()