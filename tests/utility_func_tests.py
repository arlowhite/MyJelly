__author__ = 'awhite'

# Test straigtforward calculating functions to verify edge cases

import unittest

from visuals.creatures import fix_angle

class TestNumericalFunctions(unittest.TestCase):

    def test_fix_angle(self):
        self.assertEqual(fix_angle(180), 180)
        self.assertEqual(fix_angle(361.5), 1.5)
        self.assertEqual(fix_angle(360), 0)
        self.assertEqual(fix_angle(-360), 0)

        self.assertEqual(fix_angle(-362), -2)
        self.assertEqual(fix_angle(-180), -180)

        self.assertEqual(fix_angle(181), -179)
        self.assertEqual(fix_angle(180+90+45), -45)
        self.assertEqual(fix_angle(-184), 176)
        self.assertEqual(fix_angle(-180 - 179), 1)
