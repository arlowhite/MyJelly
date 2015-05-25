from kivy.uix.floatlayout import FloatLayout
from kivy.uix.stencilview import StencilView

__author__ = 'awhite'

# Simple UIX elements
# Custom buttons, etc.

from kivy.logger import Logger
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.properties import ListProperty, StringProperty

from visuals.creatures import Jelly
from misc.exceptions import InsufficientData

class CreatureWidget(Widget):
    """Contains and centers a Creature"""

class JellySelectButton(Button):
    "Selection button displayed in JellySelectionScreen"
    # Note: Button binding done in KV

    def __init__(self, jelly_store, **kwargs):
        self.store = jelly_store
        info = jelly_store['info']
        self.jelly_id = info['id']
        self.image_filename = info['image_filepath']

        super(JellySelectButton, self).__init__(**kwargs)

        try:
            # Create moving Jelly
            pos = self.center
            print(pos)
            angle = 90
            j = Jelly(jelly_store=jelly_store, pos=pos, angle=angle, phy_group_num=1)
            # FIXME wrap in CreatureWidget
            self.jelly = j

            # Loaded successfully, remove image
            self.remove_widget(self.ids.image)


        except InsufficientData as ex:
            Logger.info("Not enough data to preview Jelly %s: %s", self.jelly_id, ex.message)

        except:
            Logger.exception("Problem previewing Jelly %s", self.jelly_id)
            raise

    def on_center(self, *args):
        if hasattr(self, 'jelly'):
            self.jelly.move(*self.center)



    def on_release(self):
        # TODO long press to edit? Other options, delete, etc. Action Menu of JellyEditor?
        print(self.last_touch)




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
