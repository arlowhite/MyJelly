__author__ = 'awhite'

import os
import unittest

from data.state_storage import *

from main import MyJellyApp


class TestAnimationConstructor(unittest.TestCase):

  def test_construct_creature(self):
      os.chdir('..')  # Image paths are relative to project root
      app = MyJellyApp()
      app.run()

      jelly_id = 'f6b069974318417183c7f820b86d7b99'
      store = load_jelly_storage(jelly_id)
      jelly = construct_creature(store)


if __name__ == '__main__':
    unittest.main()
