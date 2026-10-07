import unittest
from PIL import ImageChops
from bluey.artwork import animated_character, animation_base


class AnimationTests(unittest.TestCase):
    def test_gaze_blink_and_speech_change_visible_pixels(self):
        neutral = animated_character()
        for frame in (animated_character((1,-1)), animated_character(talk=1), animated_character(closed=1)):
            self.assertIsNotNone(ImageChops.difference(neutral.convert("RGB"), frame.convert("RGB")).getbbox())
            self.assertEqual(frame.size, (84,76))
            self.assertEqual(frame.getpixel((0,0))[3], 0)

    def test_invalid_and_outside_inputs_are_bounded(self):
        self.assertEqual(animated_character((float('nan'),float('inf'))).tobytes(), animated_character().tobytes())
        self.assertEqual(animated_character((10,-8),5,-2).tobytes(), animated_character((1,-1),1,0).tobytes())

    def test_static_skin_is_cached_and_not_modified_by_frames(self):
        base = animation_base()
        before = base.tobytes()
        animated_character((1,1),1,1)
        self.assertIs(animation_base(), base)
        self.assertEqual(base.tobytes(), before)
