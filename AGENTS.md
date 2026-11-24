# Notes for coding agents

Read this before changing `kb2pad`. User-facing docs are in [README.md](README.md).

## What this is

A single-file Linux tool (`kb2pad.py`, about 200 lines, Python 3 + `python-evdev`) that grabs one physical keyboard and exposes it as a virtual Xbox 360 pad via `uinput`. Its purpose is local co-op with two keyboards: the game sees one keyboard (player 1) and one controller (player 2).

## Architecture (kb2pad.py)

| Part | Role |
|---|---|
| `LSTICK`, `RSTICK`, `DPAD`, `BUTTONS`, `TRIGGERS` | The key map. Plain dicts of `evdev.ecodes` constants. The only thing most changes should touch. |
| `make_virtual_pad()` | Creates the `UInput` device: buttons, two sticks (±32767), two triggers (0–255), hat d-pad. Vendor/product `045e:028e` (wired Xbox 360) so Steam/SDL/Proton map it without configuration. |
| `find_keyboard(name_part)` | First `/dev/input/event*` whose name contains `name_part` and has `KEY_A` (that is, a real keyboard, not its consumer-control sibling). |
| `PadState` | Pure state machine: `handle(code, value)` → `ui.write(...)` + `ui.syn()`. Tracks held keys so diagonals, opposite-key cancelling and many-keys-to-one-button work. Ignores auto-repeat (`value == 2`). |
| `run()` | Main loop: find → `grab()` → `read_loop()` → `PadState.handle`. On `OSError` (Bluetooth sleep/disconnect) it releases all inputs and waits for the device to return. Always `ungrab()`s on exit. |

`PadState` takes any object with `write(type, code, value)` and `syn()`, which is why the tests can use a fake.

## Invariants: don't break these

- **Always ungrab on exit.** Otherwise the user's keyboard stays dead until it is replugged.
- **Release everything when the source disappears** (`release_all()`), or the character keeps running with a "stuck" key.
- **Keep diagonals normalised** (×0.7071) so diagonal speed isn't faster.
- **Keep `KEY_A` in the keyboard check**: many keyboards expose several event nodes with the same name.
- **No pip-only dependencies.** It runs under `sudo` with the system Python, so dependencies must be installable from distro packages.

## Verifying changes

1. **Unit tests (always run them; no root needed):**
   ```bash
   python3 -m unittest discover -s tests -v
   ```
   Add a test in `tests/test_mapping.py` for any mapping or `PadState` behaviour you change.
2. **Real device (needs sudo and the hardware; ask the user to run it):**
   - `sudo python3 kb2pad.py --list`, then `sudo python3 kb2pad.py --device "<name>"`.
   - Open https://hardwaretester.com/gamepad, press a key on the grabbed keyboard (browsers hide gamepads until a button is pressed), and confirm that "Microsoft X-Box 360 pad (kb2pad)" appears and that buttons and sticks react.
   - `grep -A4 kb2pad /proc/bus/input/devices` shows the virtual device. `sudo evtest` shows raw events.
3. You usually can't run step 2 yourself (root plus a second physical keyboard). Say so instead of claiming it works.

## Extension ideas (with pointers)

- **Config file:** load the five maps from TOML (`tomllib` is in the stdlib) with key names like `"KEY_SPACE"` → `getattr(ecodes, name)`. Keep the current maps as defaults.
- **Multiple players:** run one `(keyboard, UInput, PadState)` triple per `--device` and multiplex with `selectors` or `asyncio` (`evdev` supports `async_read_loop`). Give each pad a distinct name.
- **Half-tilt modifier:** in `emit_sticks()`, scale by 0.5 while a modifier key is held.
- **Mouse → right stick:** read `REL_X/REL_Y` from a chosen mouse, decay toward 0 each tick, and write `ABS_RX/ABS_RY`.
- **Rumble:** the virtual pad doesn't declare `EV_FF`. Adding it needs `UInput` force-feedback upload handling; low priority.
- **Service:** a systemd unit running as root with `--device`, or a udev rule plus an `input` group (see README, "Running without sudo").

## Style

Plain Python, no framework, single file unless a feature clearly needs a module. Keep the key map readable at the top of the file.
