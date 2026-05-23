# =========================================
# GAMECUBE CONTROLLER TESTER
# =========================================
#
# INSTALL:
#
# pip install pillow pyusb
#
# Put your controller image in the same folder:
# controller.png
# Image attribution -
# Gamecube-controller.jpg: Evan-Amos, derivative work: Alphathon™ (talk)
# Gamecube-controller.jpg, CC BY-SA 3.0,
# https://commons.wikimedia.org/w/index.php?curid=11422462
#
# =========================================

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import usb.core
import threading
import time
import math
import sys
import os

# =========================================
# USB
# =========================================

# Vendor and product IDs for the Mayflash adapter in Wii U mode.
# In PC mode the adapter presents different IDs and won't be found here.
VENDOR_ID  = 0x057e  # Nintendo
PRODUCT_ID = 0x0337  # Wii U GameCube Adapter

def init_adapter():
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

    if dev is None:
        messagebox.showerror(
            "Adapter Not Found",
            "GameCube adapter not found.\n\n"
            "Make sure the Mayflash adapter is connected and in Wii U mode."
        )
        sys.exit(1)

    try:
        dev.set_configuration()
        # Send the adapter's init command. Required to activate controller
        # polling — without it the adapter sends no data.
        dev.write(0x02, b'\x13')
    except usb.core.USBError as e:
        messagebox.showerror(
            "Could Not Open Adapter",
            f"Could not open adapter: {e}\n\n"
            "Try running the udev setup script and replugging the adapter."
        )
        sys.exit(1)

    return dev

# =========================================
# WINDOW
# =========================================

WIDTH  = 1400
HEIGHT = 950

# =========================================
# CONTROLLER IMAGE
# Position and size of the controller photo on the canvas
# =========================================

IMAGE_X = 150
IMAGE_Y = 120
IMAGE_W = 1100
IMAGE_H = 780

# =========================================
# OVERLAY COORDINATES
# All positions are relative to the top-left corner of the controller image.
# Adjust these if using a different image or scaling.
# =========================================

MAIN_X  = 271   # Main stick center
MAIN_Y  = 269

C_X     = 700   # C stick center
C_Y     = 457

A_X     = 834   # Face buttons
A_Y     = 275
B_X     = 725
B_Y     = 320
X_X     = 929
X_Y     = 254
Y_X     = 805
Y_Y     = 175

START_X = 550   # Start button
START_Y = 280

DPAD_X  = 400   # D-pad center
DPAD_Y  = 460

Z_X     = 857   # Z button center
Z_Y     = 125

# =========================================
# ANALOG CALIBRATION
# DEADZONE: minimum stick offset from center before registering.
# REST_L/R: raw byte value of each trigger at rest (unpressed).
# These were determined empirically from raw USB packet data.
# =========================================

DEADZONE = 5
REST_L   = 0x22
REST_R   = 0x25

# =========================================
# FONT
# Single definition used throughout the app for consistency
# =========================================

FONT      = "Consolas"
FONT_LG   = (FONT, 20, "bold")   # L/R/Z labels
FONT_MD   = (FONT, 18, "bold")   # trigger bar labels
FONT_BTN  = (FONT, 14, "bold")   # rumble button

# =========================================
# HELPERS
# =========================================

def apply_deadzone(value, center):
    # Returns offset from center, or 0 if within deadzone threshold.
    # Prevents idle stick noise from registering as movement.
    offset = value - center
    return 0 if abs(offset) < DEADZONE else offset


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def decode(data):
    # The adapter sends 37-byte packets covering all 4 controller ports.
    # Byte 1 is the status byte for port 1. Bit 4 indicates a controller
    # is connected — if not set, skip this packet.
    if not (data[1] & 0x10):
        return None

    # Button states are packed as individual bits across two bytes.
    b1 = data[2]  # A, B, X, Y, D-pad
    b2 = data[3]  # Start, Z, R digital, L digital

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

    # Analog axes are single bytes. Center values determined empirically.
    # Triggers are offset by their rest value so they read 0 at rest.
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
# GUI
# =========================================

class GCTEST:

    def __init__(self, root):
        self.root = root
        root.title("GameCube Controller Tester")
        root.configure(bg="black")

        self.canvas = tk.Canvas(
            root,
            width=WIDTH,
            height=HEIGHT,
            bg="black",
            highlightthickness=0
        )
        self.canvas.pack()

        self.elements = {}

        self.load_image()
        self.draw_overlay()

        # Init adapter after drawing the overlay so the window is visible
        # before any error dialogs appear
        self.dev = init_adapter()

        self.running = True
        self.thread = threading.Thread(
            target=self.poll_controller,
            daemon=True
        )
        self.thread.start()

    # =====================================
    # IMAGE
    # =====================================

    def load_image(self):
        # Resolve image path whether running as a script or PyInstaller binary.
        # sys._MEIPASS is set by PyInstaller to the temp extraction folder.
        def resource_path(filename):
            if hasattr(sys, '_MEIPASS'):
                return os.path.join(sys._MEIPASS, filename)
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

        img = Image.open(resource_path("controller.png"))
        img = img.resize((IMAGE_W, IMAGE_H))

        # Must keep a reference to prevent garbage collection
        self.controller_img = ImageTk.PhotoImage(img)

        self.canvas.create_image(
            IMAGE_X,
            IMAGE_Y,
            image=self.controller_img,
            anchor="nw"
        )

    # =====================================
    # POSITION HELPER
    # =====================================

    def pos(self, x, y):
        # Converts image-local coordinates to canvas coordinates
        return (IMAGE_X + x, IMAGE_Y + y)

    # =====================================
    # GLOW HELPERS
    # Each method draws concentric shapes to simulate a glow effect.
    # Shapes are drawn outermost first so inner layers render on top.
    # Returns a list of canvas item IDs for show/hide toggling.
    # =====================================

    def glow_circle(self, x, y, radius, color, layers=5):
        ids = []
        for i in range(layers, 0, -1):
            expand = i * 4
            oid = self.canvas.create_oval(
                x-radius-expand, y-radius-expand,
                x+radius+expand, y+radius+expand,
                outline=color,
                width=2
            )
            ids.append(oid)
        return ids

    def glow_rounded_rect(self, x1, y1, x2, y2, radius, color, layers=4):
        # Uses a smooth polygon to approximate a rounded rectangle.
        # smooth=True causes tkinter to draw bezier curves through the points.
        ids = []
        for i in range(layers, 0, -1):
            expand = i * 3
            ex1 = x1 - expand
            ey1 = y1 - expand
            ex2 = x2 + expand
            ey2 = y2 + expand
            r = radius + expand
            oid = self.canvas.create_polygon(
                ex1+r, ey1,  ex2-r, ey1,
                ex2,   ey1,  ex2,   ey1+r,
                ex2,   ey2-r, ex2,  ey2,
                ex2-r, ey2,  ex1+r, ey2,
                ex1,   ey2,  ex1,   ey2-r,
                ex1,   ey1+r, ex1,  ey1,
                smooth=True,
                fill='',
                outline=color,
                width=2
            )
            ids.append(oid)
        return ids

    # =====================================
    # RUMBLE
    # =====================================

    def rumble(self, duration_ms=500):
        try:
            # Rumble packet: command byte 0x11, then one byte per port.
            # 0x01 = rumble on, 0x00 = off. Only port 1 is activated here.
            self.dev.write(0x02, b'\x11\x01\x00\x00\x00')
            # Schedule automatic stop after duration
            self.root.after(duration_ms, self.rumble_stop)
        except usb.core.USBError as e:
            print(f"Rumble error: {e}")

    def rumble_stop(self):
        try:
            self.dev.write(0x02, b'\x11\x00\x00\x00\x00')
        except usb.core.USBError as e:
            print(f"Rumble stop error: {e}")

    # =====================================
    # DRAW OVERLAY
    # =====================================

    def draw_overlay(self):
        c = self.canvas

        # =================================
        # MAIN STICK
        # Decorative ring with tick marks, plus a movable dot
        # =================================

        mx, my = self.pos(MAIN_X, MAIN_Y)

        c.create_oval(
            mx-105, my-105, mx+105, my+105,
            outline="#2d7dff",
            width=4
        )

        # Tick marks at 45 degree intervals
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x1 = mx + math.cos(rad) * 92
            y1 = my + math.sin(rad) * 92
            x2 = mx + math.cos(rad) * 105
            y2 = my + math.sin(rad) * 105
            c.create_line(x1, y1, x2, y2, fill="#59b2ff", width=3)

        self.elements['main_dot'] = c.create_oval(
            mx-15, my-15, mx+15, my+15,
            fill="#a9dbff",
            outline="white",
            width=2
        )

        # =================================
        # C STICK
        # Ring and movable dot in GC yellow
        # =================================

        cx, cy = self.pos(C_X, C_Y)

        c.create_oval(
            cx-58, cy-58, cx+58, cy+58,
            outline="#ffcc00",
            width=4
        )

        self.elements['c_dot'] = c.create_oval(
            cx-12, cy-12, cx+12, cy+12,
            fill="#ffd84d",
            outline="#fff3a8",
            width=2
        )

        # =================================
        # FACE BUTTONS
        # A and B use circles; X and Y use rounded rects
        # to better match their physical shapes
        # =================================

        ax, ay = self.pos(A_X, A_Y)
        bx, by = self.pos(B_X, B_Y)
        xx, xy = self.pos(X_X, X_Y)
        yx, yy = self.pos(Y_X, Y_Y)
        sx, sy = self.pos(START_X, START_Y)

        self.elements['A']     = self.glow_circle(ax, ay, 50, "#00ff99")
        self.elements['B']     = self.glow_circle(bx, by, 28, "#ff3355")
        self.elements['Start'] = self.glow_circle(sx, sy, 18, "#ffffff")

        # X is a vertical capsule, Y is a horizontal capsule
        self.elements['X'] = self.glow_rounded_rect(
            xx-18, xy-40, xx+18, xy+40, radius=18, color="#ffffff"
        )
        self.elements['Y'] = self.glow_rounded_rect(
            yx-42, yy-18, yx+42, yy+18, radius=18, color="#ffffff"
        )

        # =================================
        # Z BUTTON
        # Horizontal capsule with permanent label
        # =================================

        zx, zy = self.pos(Z_X, Z_Y)

        self.elements['Z'] = self.glow_rounded_rect(
            zx-70, zy-18, zx+70, zy+18, radius=12, color="#bb66ff"
        )

        c.create_text(zx, zy, text="Z", fill="#bb66ff", font=FONT_LG)

        # =================================
        # D-PAD
        # Four separate rounded rects, one per direction
        # =================================

        dx, dy = self.pos(DPAD_X, DPAD_Y)

        self.elements['D-Up'] = self.glow_rounded_rect(
            dx-14, dy-58, dx+14, dy-26, radius=8, color="#4da6ff"
        )
        self.elements['D-Down'] = self.glow_rounded_rect(
            dx-14, dy+26, dx+14, dy+58, radius=8, color="#4da6ff"
        )
        self.elements['D-Left'] = self.glow_rounded_rect(
            dx-58, dy-14, dx-26, dy+14, radius=8, color="#4da6ff"
        )
        self.elements['D-Right'] = self.glow_rounded_rect(
            dx+26, dy-14, dx+58, dy+14, radius=8, color="#4da6ff"
        )

        # =================================
        # L/R DIGITAL PRESS INDICATORS
        # Glowing circles that light up on full trigger press.
        # Symmetric around window center (x=700).
        # =================================

        L_CIRCLE_X = 250
        R_CIRCLE_X = 1150
        CIRCLE_Y   = 120

        c.create_text(L_CIRCLE_X, 60, text="L", fill="#66b8ff", font=FONT_LG)
        c.create_text(R_CIRCLE_X, 60, text="R", fill="#66b8ff", font=FONT_LG)

        self.elements['L'] = self.glow_circle(L_CIRCLE_X, CIRCLE_Y, 16, "#33aaff")
        self.elements['R'] = self.glow_circle(R_CIRCLE_X, CIRCLE_Y, 16, "#33aaff")

        # =================================
        # TRIGGER BARS
        # Analog fill bars, symmetric around window center.
        # L bar: 310-530, R bar: 870-1090 (gap of 340px centered on 700)
        # =================================

        BAR_W    = 220
        BAR_Y1   = 85
        BAR_Y2   = 108
        L_BAR_X1 = 310
        L_BAR_X2 = L_BAR_X1 + BAR_W   # 530
        R_BAR_X2 = 1090
        R_BAR_X1 = R_BAR_X2 - BAR_W   # 870

        c.create_text(
            (L_BAR_X1 + L_BAR_X2) // 2, BAR_Y1 - 22,
            text="L TRIGGER", fill="#66b8ff", font=FONT_MD
        )
        c.create_rectangle(
            L_BAR_X1, BAR_Y1, L_BAR_X2, BAR_Y2,
            fill="#111111", outline="#666666"
        )
        self.elements['L_bar'] = c.create_rectangle(
            L_BAR_X1, BAR_Y1, L_BAR_X1, BAR_Y2,
            fill="#4da6ff", outline=""
        )

        c.create_text(
            (R_BAR_X1 + R_BAR_X2) // 2, BAR_Y1 - 22,
            text="R TRIGGER", fill="#66b8ff", font=FONT_MD
        )
        c.create_rectangle(
            R_BAR_X1, BAR_Y1, R_BAR_X2, BAR_Y2,
            fill="#111111", outline="#666666"
        )
        self.elements['R_bar'] = c.create_rectangle(
            R_BAR_X1, BAR_Y1, R_BAR_X1, BAR_Y2,
            fill="#4da6ff", outline=""
        )

        # =================================
        # RUMBLE BUTTON
        # =================================

        self.rumble_btn = tk.Button(
            self.root,
            text="TEST RUMBLE",
            command=self.rumble,
            font=FONT_BTN,
            bg="#1a1a2e",
            fg="#66b8ff",
            activebackground="#2a2a4e",
            activeforeground="#ffffff",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2"
        )
        self.canvas.create_window(WIDTH // 2, HEIGHT - 150, window=self.rumble_btn)

        # Hide all glow elements initially — they show only when inputs are active
        for k, v in self.elements.items():
            if isinstance(v, list):
                for item in v:
                    c.itemconfigure(item, state='hidden')

    # =====================================
    # GLOW CONTROL
    # =====================================

    def set_glow(self, name, active):
        # Show or hide all layers of a glow element
        for item in self.elements[name]:
            self.canvas.itemconfigure(
                item,
                state='normal' if active else 'hidden'
            )

    # =====================================
    # STICK UPDATE
    # Moves the stick dot based on axis values.
    # Axis values range roughly -100 to +100 after deadzone is applied.
    # =====================================

    def update_stick(self, name, x, y, cx, cy, radius):
        tx = cx + int((x / 100) * radius)
        ty = cy - int((y / 100) * radius)  # Y is inverted (canvas y increases downward)
        tx = clamp(tx, cx-radius, cx+radius)
        ty = clamp(ty, cy-radius, cy+radius)
        r = 14
        self.canvas.coords(self.elements[name], tx-r, ty-r, tx+r, ty+r)

    # =====================================
    # TRIGGER BAR
    # Fills the bar rectangle proportionally to trigger value (0-180)
    # =====================================

    def update_trigger_bar(self, name, value, x1, x2, y1, y2):
        value = clamp(value, 0, 180)
        fill = x1 + int((value / 180) * (x2 - x1))
        self.canvas.coords(self.elements[name], x1, y1, fill, y2)

    # =====================================
    # GUI UPDATE
    # Called from the main thread via root.after() on each polling cycle
    # =====================================

    def update_gui(self, buttons, axes):
        # Update all button glows
        for btn in [
            'A', 'B', 'X', 'Y', 'Start', 'Z',
            'D-Up', 'D-Down', 'D-Left', 'D-Right',
            'L', 'R'
        ]:
            self.set_glow(btn, buttons[btn])

        # Update main stick dot position
        mx, my = self.pos(MAIN_X, MAIN_Y)
        self.update_stick('main_dot', axes['Main X'], axes['Main Y'], mx, my, 72)

        # Update C stick dot position
        cx, cy = self.pos(C_X, C_Y)
        self.update_stick('c_dot', axes['C X'], axes['C Y'], cx, cy, 40)

        # Update trigger fill bars
        self.update_trigger_bar('L_bar', axes['L Trig'], 310, 530, 85, 108)
        self.update_trigger_bar('R_bar', axes['R Trig'], 870, 1090, 85, 108)

    # =====================================
    # POLLING
    # Runs in a background thread. Reads USB packets and schedules
    # GUI updates on the main thread via root.after() to keep tkinter thread-safe.
    # =====================================

    def poll_controller(self):
        while self.running:
            try:
                data = self.dev.read(0x81, 37, timeout=1000)
                result = decode(data)
                if result:
                    buttons, axes = result
                    self.root.after(0, self.update_gui, buttons, axes)
            except usb.core.USBTimeoutError:
                pass
            except Exception as e:
                print("ERROR:", e)
            time.sleep(0.005)

    # =====================================
    # CLOSE
    # =====================================

    def close(self):
        self.running = False
        self.root.destroy()

# =========================================
# MAIN
# =========================================

root = tk.Tk()
app = GCTEST(root)
root.protocol("WM_DELETE_WINDOW", app.close)
root.mainloop()