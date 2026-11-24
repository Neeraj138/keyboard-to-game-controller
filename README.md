# keyboard-to-game-controller (kb2pad)

Turn a **second keyboard into an Xbox 360 controller** on Linux, so two people can play local co-op on one computer with two keyboards and no gamepad.

Games treat every keyboard as the same keyboard, so plugging in a second one doesn't give you a second player. `kb2pad` fixes that:

- **Player 1:** the laptop keyboard (and mouse/touchpad), as usual.
- **Player 2:** the second keyboard (USB or Bluetooth). `kb2pad` takes it over and the system sees an **Xbox 360 controller** instead.

Built for *It Takes Two* (keyboard + controller co-op), but it works for any game that supports one keyboard player and one controller player.

## How it works

1. Finds the second keyboard by name (via `evdev`).
2. **Grabs** it, so its keys stop typing into the game or desktop.
3. Creates a virtual **Microsoft X-Box 360 pad** with `uinput` (same USB IDs as the real thing: `045e:028e`), which Steam, Proton and SDL recognise right away.
4. Turns key presses into stick, button and trigger events.

When you stop it (Ctrl+C), the keyboard is released and types normally again.

## Requirements

- Linux with `uinput` (any modern distro).
- Python 3 and [python-evdev](https://python-evdev.readthedocs.io/).

```bash
# Fedora
sudo dnf install python3-evdev
# Debian / Ubuntu
sudo apt install python3-evdev
# Arch
sudo pacman -S python-evdev
```

Install it system-wide (not in a virtualenv): the script runs under `sudo`, which uses the system Python.

## Usage

```bash
# 1. Find your second keyboard's name
sudo python3 kb2pad.py --list

# 2. Start it (default name match: "MX Keys Mini")
sudo python3 kb2pad.py --device "MX Keys Mini"
```

Use any part of the name shown by `--list`. Leave the terminal open while you play. Stop with **Ctrl+C typed on the other keyboard**, since the grabbed one is no longer a keyboard.

If the keyboard sleeps or disconnects (common with Bluetooth), `kb2pad` waits and grabs it again when it comes back.

### In the game

- Player 1 uses keyboard and mouse, player 2 uses the controller.
- On Steam, if the pad isn't detected: **Steam → Settings → Controller → enable "Xbox Configuration Support"**.

## Player 2 controls

| Keys | Controller |
|---|---|
| W A S D | Left stick (move) |
| I J K L | Right stick (camera) |
| Space | A |
| Left Shift | B |
| R | X |
| E | Y |
| Q / P | LB / RB |
| U / O | LT / RT |
| Left Ctrl / M | L3 / R3 |
| Arrow keys | D-pad |
| Tab | Back / View |
| Enter or Esc | Start / Menu |
| Backspace | Guide |

To change them, edit the `KEY MAP` section at the top of `kb2pad.py`.

## Testing it

### 1. Unit tests (no root, no hardware)

```bash
python3 -m unittest discover -s tests -v
```

These check the key → stick/button/trigger mapping with a fake output device.

### 2. Gamepad tester website (real hardware)

1. Start `sudo python3 kb2pad.py`. You should see:
   ```
   Virtual controller created: /dev/input/eventNN
   Grabbed 'Logitech MX Keys Mini' (/dev/input/eventMM). It is now a controller. Ctrl+C to stop.
   ```
2. Open **https://hardwaretester.com/gamepad** in your browser.
3. **Press any key on the second keyboard** first: browsers only reveal a gamepad after you press one of its buttons.
4. The page should list **"Microsoft X-Box 360 pad (kb2pad)"** and show a controller diagram:
   - **Space**, **Shift**, **R**, **E** light up the face buttons.
   - **WASD** moves the left stick dot, **IJKL** the right stick dot.
   - **U / O** fill the triggers, **arrow keys** light the d-pad.
5. The second keyboard should **not** type anything into the page while `kb2pad` runs. If it does, the grab failed (see Troubleshooting).

### 3. Command-line checks

```bash
grep -A4 kb2pad /proc/bus/input/devices    # the virtual pad exists
sudo evtest                                # pick the kb2pad device and press keys
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `python-evdev missing` | Install the distro package above. Under `sudo`, a pip install in a venv isn't visible. |
| `Waiting for keyboard matching ...` | Wrong name, or the keyboard is asleep. Press a key on it, check `--list`, pass `--device "<part of name>"`. |
| `Permission denied` | Run with `sudo`, or see "Running without sudo" below. |
| Game doesn't see the controller | Steam: enable Xbox Configuration Support. Restart the game after starting `kb2pad`. |
| Steam shows two controllers | Steam Input may wrap the virtual pad. Disable Steam Input for that game, or pick the right one in the game's menu. |
| Keys still type into the game | Another program grabbed the keyboard first, or the name matched a different device. Check `--list`. |

### Running without sudo (optional)

Give your user access to input devices and `uinput`. This lets any program you run read all keyboards, so only do it on a machine you trust:

```bash
sudo usermod -aG input $USER
echo 'KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"' | sudo tee /etc/udev/rules.d/99-kb2pad-uinput.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
# log out and back in
```

## Project layout

```
kb2pad.py              the whole tool: device discovery, grab, virtual pad, key mapping
tests/test_mapping.py  unit tests for the mapping (fake uinput, no root)
AGENTS.md              notes for coding agents extending this project
```

## Building on it

See [AGENTS.md](AGENTS.md) for the architecture, how to add features, and how to verify changes. Ideas:

- A config file (TOML/JSON) for key maps instead of editing the script.
- Several keyboards → several pads (3–4 player couch co-op).
- Analog feel: hold a modifier for half-tilt walking.
- Mouse → right stick for player 2.
- A systemd user service or a tray toggle.
