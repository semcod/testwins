"""Plain Playwright pages must not be mistaken for FrameSurface wrappers.

Playwright's Page has a `frame()` method, so `hasattr(page, 'frame')` is
always true and the runner called `page.frame.evaluate(...)` on a bound
method: axe never ran ("axe-core did not complete") and URL assertions on
ordinary pages failed.
"""
from testwins.frames import FrameSurface
from testwins.runner import _surface


class PlainPage:
    def frame(self, name=None, url=None):  # same shape as playwright Page.frame
        return None


def test_plain_page_is_its_own_surface():
    page = PlainPage()
    assert _surface(page) is page


def test_frame_surface_resolves_to_its_frame():
    frame = object()
    surface = FrameSurface(page=None, handle=None, frame=frame, definition={}, masks=[], box={'width': 1, 'height': 1})
    assert _surface(surface) is frame
