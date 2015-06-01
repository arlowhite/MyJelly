__author__ = 'awhite'

# Not actually that useful now, GUI is going to change too much
# Need to think about value of GUI testing

import os
import unittest

import main
from main import MyJellyApp

class TestAnimationConstructor(unittest.TestCase):

  def test_upper(self):
      os.chdir('..')  # Image paths are relative to project root
      app = MyJellyApp()
      app.run()


if __name__ == '__main__':
    unittest.main()
