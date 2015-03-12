__author__ = 'awhite'

# Simple UIX elements
# Custom buttons, etc.

from kivy.uix.button import Button
from data.jelly import JellyData

class JellySelectButton(Button):
    "Selection button displayed in JellySelectionScreen"
    # Note: Button binding done in KV

    def __init__(self, jelly_data, **kwargs):
        self.jelly_data = jelly_data
        super(JellySelectButton, self).__init__(**kwargs)


        #with self.canvas:

