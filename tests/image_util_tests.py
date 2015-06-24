__author__ = 'awhite'

import unittest

from kivy.core.image import Image as CoreImage

from image_util import determine_colored_rows, layout_circles_on_rows

class TestAnimationConstructor(unittest.TestCase):

    def test_determine_colored_rows(self):
        img_filename = '/home/awhite/Pictures/Artwork/testing_tentacle.png'
        # keep_data didn't seem to make a difference, but maybe depends on the loader used?
        img = CoreImage(img_filename, keep_data=True)
        rows = determine_colored_rows(img)
        print(rows)
        self.assertEqual(5, len(rows))

    def test_layout_circles_on_rows(self):
        rows = [(0, 0, 2), (1, 0, 2), (2, 1, 1), (3, 1, 1), (4, 1, 1)]
        circles = layout_circles_on_rows(rows, radius_spacing=0.2)
        print('circles', circles)

        for c in circles:
            self.assertGreater(c[2], 0, 'Radius not greater than zero! {}'.format(c))


if __name__ == '__main__':
    unittest.main()
