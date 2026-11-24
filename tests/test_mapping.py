"""Unit tests for the key -> gamepad mapping. No root, no real devices needed.

Run:  python3 -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evdev import ecodes as e  # noqa: E402

import kb2pad  # noqa: E402


class FakeUInput:
    """Records what PadState writes, keeping the latest value per (type, code)."""

    def __init__(self):
        self.state = {}
        self.syncs = 0

    def write(self, etype, code, value):
        self.state[(etype, code)] = value

    def syn(self):
        self.syncs += 1


DOWN, UP, REPEAT = 1, 0, 2


class MappingTest(unittest.TestCase):
    def setUp(self):
        self.ui = FakeUInput()
        self.pad = kb2pad.PadState(self.ui)

    def key(self, code, value):
        self.pad.handle(code, value)

    def test_space_is_a_button(self):
        self.key(e.KEY_SPACE, DOWN)
        self.assertEqual(self.ui.state[(e.EV_KEY, e.BTN_SOUTH)], 1)
        self.key(e.KEY_SPACE, UP)
        self.assertEqual(self.ui.state[(e.EV_KEY, e.BTN_SOUTH)], 0)

    def test_wasd_moves_left_stick(self):
        self.key(e.KEY_D, DOWN)
        self.assertEqual(self.ui.state[(e.EV_ABS, e.ABS_X)], kb2pad.STICK_MAX)
        self.assertEqual(self.ui.state[(e.EV_ABS, e.ABS_Y)], 0)
        self.key(e.KEY_W, DOWN)                      # diagonal: stays on the unit circle
        x = self.ui.state[(e.EV_ABS, e.ABS_X)]
        y = self.ui.state[(e.EV_ABS, e.ABS_Y)]
        self.assertGreater(x, 0)
        self.assertLess(y, 0)
        self.assertAlmostEqual((x * x + y * y) ** 0.5, kb2pad.STICK_MAX, delta=50)
        self.key(e.KEY_D, UP)
        self.key(e.KEY_W, UP)
        self.assertEqual(self.ui.state[(e.EV_ABS, e.ABS_X)], 0)
        self.assertEqual(self.ui.state[(e.EV_ABS, e.ABS_Y)], 0)

    def test_opposite_keys_cancel(self):
        self.key(e.KEY_A, DOWN)
        self.key(e.KEY_D, DOWN)
        self.assertEqual(self.ui.state[(e.EV_ABS, e.ABS_X)], 0)

    def test_ijkl_moves_right_stick(self):
        self.key(e.KEY_J, DOWN)
        self.assertEqual(self.ui.state[(e.EV_ABS, e.ABS_RX)], -kb2pad.STICK_MAX)

    def test_triggers(self):
        self.key(e.KEY_O, DOWN)
        self.assertEqual(self.ui.state[(e.EV_ABS, e.ABS_RZ)], kb2pad.TRIG_MAX)
        self.key(e.KEY_O, UP)
        self.assertEqual(self.ui.state[(e.EV_ABS, e.ABS_RZ)], 0)

    def test_arrows_are_dpad(self):
        self.key(e.KEY_UP, DOWN)
        self.assertEqual(self.ui.state[(e.EV_ABS, e.ABS_HAT0Y)], -1)

    def test_two_keys_one_button(self):
        # Enter and Esc both map to Start: releasing one must not release Start
        self.key(e.KEY_ENTER, DOWN)
        self.key(e.KEY_ESC, DOWN)
        self.key(e.KEY_ENTER, UP)
        self.assertEqual(self.ui.state[(e.EV_KEY, e.BTN_START)], 1)
        self.key(e.KEY_ESC, UP)
        self.assertEqual(self.ui.state[(e.EV_KEY, e.BTN_START)], 0)

    def test_autorepeat_ignored(self):
        self.key(e.KEY_SPACE, DOWN)
        n = self.ui.syncs
        self.key(e.KEY_SPACE, REPEAT)
        self.assertEqual(self.ui.syncs, n)

    def test_unmapped_key_sends_nothing(self):
        self.key(e.KEY_Z, DOWN)
        self.assertEqual(self.ui.state, {})

    def test_release_all(self):
        self.key(e.KEY_SPACE, DOWN)
        self.key(e.KEY_D, DOWN)
        self.key(e.KEY_U, DOWN)
        self.pad.release_all()
        self.assertEqual(self.ui.state[(e.EV_KEY, e.BTN_SOUTH)], 0)
        self.assertEqual(self.ui.state[(e.EV_ABS, e.ABS_X)], 0)
        self.assertEqual(self.ui.state[(e.EV_ABS, e.ABS_Z)], 0)


if __name__ == "__main__":
    unittest.main()
