#!/usr/bin/env python3
"""
kb2pad — turn ONE specific keyboard into a virtual Xbox 360 controller.

Use case: two people, one laptop, local co-op (e.g. It Takes Two).
  Player 1: laptop keyboard + touchpad/mouse  -> plays as "Keyboard & Mouse"
  Player 2: Bluetooth keyboard                -> this script grabs it, so its
            keys no longer type anything, and exposes it as an Xbox pad.

The game sees one keyboard + one controller, which is exactly the setup it
supports for local co-op.

Run:  sudo python3 kb2pad.py            (auto-finds "MX Keys Mini")
      sudo python3 kb2pad.py --list     (show input devices)
      sudo python3 kb2pad.py --device "Some Keyboard Name"
Stop: Ctrl+C in the terminal (type it on the LAPTOP keyboard — the grabbed
      keyboard is no longer a keyboard while this runs).
"""

import argparse
import sys
import time

try:
    import evdev
    from evdev import UInput, AbsInfo, ecodes as e
except ImportError:
    sys.exit("python-evdev missing. Install it:  sudo dnf install python3-evdev")

DEFAULT_DEVICE = "MX Keys Mini"

# ---------------------------------------------------------------------------
# KEY MAP — edit freely.  Left hand on WASD, right hand on IJKL.
# ---------------------------------------------------------------------------
# Left stick (movement)
LSTICK = {"up": e.KEY_W, "down": e.KEY_S, "left": e.KEY_A, "right": e.KEY_D}
# Right stick (camera)
RSTICK = {"up": e.KEY_I, "down": e.KEY_K, "left": e.KEY_J, "right": e.KEY_L}
# D-pad
DPAD = {"up": e.KEY_UP, "down": e.KEY_DOWN, "left": e.KEY_LEFT, "right": e.KEY_RIGHT}

# Keyboard key -> gamepad button
BUTTONS = {
    e.KEY_SPACE: e.BTN_SOUTH,       # A  (jump)
    e.KEY_LEFTSHIFT: e.BTN_EAST,    # B  (dash/crouch in most games)
    e.KEY_E: e.BTN_NORTH,           # Y  (Xbox Y is BTN_NORTH under Linux)
    e.KEY_R: e.BTN_WEST,            # X
    e.KEY_Q: e.BTN_TL,              # LB
    e.KEY_P: e.BTN_TR,              # RB
    e.KEY_LEFTCTRL: e.BTN_THUMBL,   # L3 (click left stick)
    e.KEY_M: e.BTN_THUMBR,          # R3 (click right stick)
    e.KEY_TAB: e.BTN_SELECT,        # Back / View
    e.KEY_ENTER: e.BTN_START,       # Start / Menu
    e.KEY_ESC: e.BTN_START,         # Start / Menu (alt)
    e.KEY_BACKSPACE: e.BTN_MODE,    # Guide / Xbox button
}
# Keyboard key -> trigger (pressed = fully pulled)
TRIGGERS = {
    e.KEY_U: e.ABS_Z,               # LT (aim)
    e.KEY_O: e.ABS_RZ,              # RT (shoot/use)
}
# ---------------------------------------------------------------------------

STICK_MAX = 32767
TRIG_MAX = 255


def make_virtual_pad():
    stick = AbsInfo(value=0, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)
    trig = AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)
    hat = AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)
    caps = {
        e.EV_KEY: sorted(set(BUTTONS.values())
                         | {e.BTN_SOUTH, e.BTN_EAST, e.BTN_NORTH, e.BTN_WEST,
                            e.BTN_TL, e.BTN_TR, e.BTN_SELECT, e.BTN_START,
                            e.BTN_MODE, e.BTN_THUMBL, e.BTN_THUMBR}),
        e.EV_ABS: [
            (e.ABS_X, stick), (e.ABS_Y, stick),
            (e.ABS_RX, stick), (e.ABS_RY, stick),
            (e.ABS_Z, trig), (e.ABS_RZ, trig),
            (e.ABS_HAT0X, hat), (e.ABS_HAT0Y, hat),
        ],
    }
    # Pretend to be a wired Xbox 360 pad: Steam/Proton/SDL recognise it instantly.
    return UInput(caps, name="Microsoft X-Box 360 pad (kb2pad)",
                  vendor=0x045E, product=0x028E, version=0x110, bustype=e.BUS_USB)


def find_keyboard(name_part):
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        caps = dev.capabilities().get(e.EV_KEY, [])
        if name_part.lower() in dev.name.lower() and e.KEY_A in caps:
            return dev
        dev.close()
    return None


def list_devices():
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        kb = e.KEY_A in dev.capabilities().get(e.EV_KEY, [])
        print(f"{path:22} {'[keyboard] ' if kb else '           '}{dev.name}")


class PadState:
    def __init__(self, ui):
        self.ui = ui
        self.held = set()

    def axis_pair(self, group):
        x = (group["right"] in self.held) - (group["left"] in self.held)
        y = (group["down"] in self.held) - (group["up"] in self.held)
        return x, y

    def emit_sticks(self):
        for group, ax, ay in ((LSTICK, e.ABS_X, e.ABS_Y), (RSTICK, e.ABS_RX, e.ABS_RY)):
            x, y = self.axis_pair(group)
            scale = STICK_MAX * (0.7071 if x and y else 1.0)  # keep diagonals on the unit circle
            self.ui.write(e.EV_ABS, ax, int(x * scale))
            self.ui.write(e.EV_ABS, ay, int(y * scale))
        hx, hy = self.axis_pair(DPAD)
        self.ui.write(e.EV_ABS, e.ABS_HAT0X, hx)
        self.ui.write(e.EV_ABS, e.ABS_HAT0Y, hy)

    def handle(self, code, value):
        if value == 2:          # key auto-repeat: irrelevant for a pad
            return
        pressed = value == 1
        if pressed:
            self.held.add(code)
        else:
            self.held.discard(code)

        if code in BUTTONS:
            # Several keys may map to one button (Enter/Esc -> Start)
            btn = BUTTONS[code]
            down = any(k in self.held for k, b in BUTTONS.items() if b == btn)
            self.ui.write(e.EV_KEY, btn, int(down))
        elif code in TRIGGERS:
            self.ui.write(e.EV_ABS, TRIGGERS[code], TRIG_MAX if pressed else 0)
        elif any(code in g.values() for g in (LSTICK, RSTICK, DPAD)):
            self.emit_sticks()
        else:
            return
        self.ui.syn()

    def release_all(self):
        self.held.clear()
        for btn in set(BUTTONS.values()):
            self.ui.write(e.EV_KEY, btn, 0)
        for ax in TRIGGERS.values():
            self.ui.write(e.EV_ABS, ax, 0)
        self.emit_sticks()
        self.ui.syn()


def run(device_name):
    ui = make_virtual_pad()
    state = PadState(ui)
    print(f"Virtual controller created: {ui.device.path if ui.device else ui}")
    try:
        while True:
            kb = find_keyboard(device_name)
            if kb is None:
                print(f"Waiting for keyboard matching '{device_name}'... "
                      "(is it on/connected? try --list)")
                time.sleep(2)
                continue
            print(f"Grabbed '{kb.name}' ({kb.path}). It is now a controller. Ctrl+C to stop.")
            try:
                kb.grab()
                for ev in kb.read_loop():
                    if ev.type == e.EV_KEY:
                        state.handle(ev.code, ev.value)
            except OSError:
                # Bluetooth keyboard went to sleep / disconnected — wait for it.
                print("Keyboard disconnected. Waiting for it to come back...")
                state.release_all()
                time.sleep(1)
            finally:
                try:
                    kb.ungrab()
                except OSError:
                    pass
                kb.close()
    except KeyboardInterrupt:
        print("\nStopping. Keyboard released.")
    finally:
        state.release_all()
        ui.close()


def main():
    ap = argparse.ArgumentParser(description="Turn one keyboard into a virtual Xbox controller.")
    ap.add_argument("--device", default=DEFAULT_DEVICE,
                    help=f"part of the keyboard's name (default: '{DEFAULT_DEVICE}')")
    ap.add_argument("--list", action="store_true", help="list input devices and exit")
    args = ap.parse_args()
    if args.list:
        list_devices()
        return
    run(args.device)


if __name__ == "__main__":
    main()
