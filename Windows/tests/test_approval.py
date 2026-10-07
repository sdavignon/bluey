import unittest
from bluey.approval import bubble_bounds


class ApprovalBoundsTests(unittest.TestCase):
    def assert_inside(self, result, monitor):
        x, y, width, height = result
        left, top, right, bottom = monitor
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)
        self.assertGreaterEqual(x, left)
        self.assertGreaterEqual(y, top)
        self.assertLessEqual(x + width, right)
        self.assertLessEqual(y + height, bottom)

    def test_negative_secondary_monitor(self):
        monitor = (-1920, -200, 0, 880)
        result = bubble_bounds((-1700, -100), monitor)
        self.assertEqual(result, (-1700, -100, 500, 310))
        self.assert_inside(result, monitor)

    def test_right_secondary_monitor_bottom_edge(self):
        monitor = (1920, 100, 4480, 1540)
        result = bubble_bounds((4479, 1539), monitor)
        self.assertEqual(result, (3980, 1230, 500, 310))
        self.assert_inside(result, monitor)

    def test_primary_right_edge_and_offscreen_anchor(self):
        monitor = (0, 0, 1920, 1080)
        self.assertEqual(bubble_bounds((1900, 300), monitor), (1420, 300, 500, 310))
        for anchor in [(-2500, -900), (9000, 9000), (1920, 1080)]:
            self.assert_inside(bubble_bounds(anchor, monitor), monitor)

    def test_monitor_above_primary_with_negative_y(self):
        monitor = (-300, -1440, 2260, 0)
        result = bubble_bounds((2250, -10), monitor)
        self.assertEqual(result, (1760, -310, 500, 310))
        self.assert_inside(result, monitor)

    def test_small_monitor_shrinks_entire_bubble(self):
        monitor = (-320, 80, 0, 280)
        result = bubble_bounds((-10, 270), monitor)
        self.assertEqual(result, (-320, 80, 320, 200))
        self.assert_inside(result, monitor)

    def test_anchor_from_old_monitor_clamps_to_current_monitor(self):
        monitor = (1920, 0, 3840, 1080)
        result = bubble_bounds((-1200, 200), monitor)
        self.assertEqual(result, (1920, 200, 500, 310))
        self.assert_inside(result, monitor)

if __name__ == '__main__':
    unittest.main()
