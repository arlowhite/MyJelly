from kivy.uix.floatlayout import FloatLayout
from kivy.uix.stencilview import StencilView

__author__ = 'awhite'

# Simple UIX elements
# Custom buttons, etc.

from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.properties import ListProperty, StringProperty

class JellySelectButton(Button):
    "Selection button displayed in JellySelectionScreen"
    # Note: Button binding done in KV

    def __init__(self, jelly_store, **kwargs):
        self.store = jelly_store
        info = jelly_store['info']
        self.jelly_id = info['id']
        self.image_filename = info['image_filepath']

        super(JellySelectButton, self).__init__(**kwargs)




class FloatLayoutStencilView(FloatLayout, StencilView):
    pass

class LabeledSpinner(Spinner):
    """A Spinner that separates the label from the value by adding
    text_values and text_value"""

    text_values = ListProperty()
    # TODO setter should adjust value
    text_value = StringProperty()

    # Kivy properties only call when changed, which protects from infinite loop
    def on_text(self, _, text):
        self.text_value = self.text_values[self.values.index(text)]

    def on_text_value(self, _, text_value):
        self.text = self.values[self.text_values.index(text_value)]
