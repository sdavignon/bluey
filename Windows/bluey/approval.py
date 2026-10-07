"""Keep Bluey's approval bubble next to the character on its current monitor."""


def bubble_bounds(anchor, monitor, size=(500, 310)):
    left, top, right, bottom = monitor
    width, height = min(size[0], right-left), min(size[1], bottom-top)
    x = max(left, min(int(anchor[0]), right-width))
    y = max(top, min(int(anchor[1]), bottom-height))
    return x, y, width, height
