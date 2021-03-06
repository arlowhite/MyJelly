from kivy.uix.floatlayout import FloatLayout
from kivy.uix.stencilview import StencilView

__author__ = 'awhite'

# Simple UIX elements
# Custom buttons, etc.

from kivy.logger import Logger
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ListProperty, StringProperty
from kivy.clock import Clock

import cymunk as phy

from visuals.creatures.jelly import JellyBell
from misc.exceptions import InsufficientData
from data.state_storage import construct_creature
from misc.physics_util import cleanup_space


class CreatureWidget(Widget):
    """Contains and centers a Creature"""

    def set_creature(self, creature):
        self.update_interval = 1/60.0
        self.creature = creature
        creature.pos = self.center

        self.phy_space = phy.Space()
        creature.bind_environment(self)
        self.canvas.add(creature.canvas)

        Clock.schedule_interval(self.update_simulation, self.update_interval)

    def update_simulation(self, dt):
        self.phy_space.step(self.update_interval)
        self.creature.update(dt)
        # Reset position to center
        self.creature.pos = self.center

    def on_center(self, _, center):
        if hasattr(self, 'creature'):
            self.creature.pos = center

    def destroy(self):
        Logger.debug('%s: destroy() unschedule update_simulation and cleanup space', self.__class__.__name__)
        Clock.unschedule(self.update_simulation)

        # if set_creature was called and phy_space set
        if hasattr(self, 'phy_space'):
            cleanup_space(self.phy_space)
            self.phy_space = None

    # def on_size(self):
    #     pass

        # FIXME old KV code for Image
        # Image:
        # id: image
        # source: root.image_filename
        # pos: root.pos
        # size: root.size
        # allow_stretch: True


class JellySelectButton(Button):
    "Selection button displayed in JellySelectionScreen"
    # Note: Button binding done in KV

    def __init__(self, jelly_store, **kwargs):
        self.store = jelly_store
        self.creature_id = jelly_store.creature_id
        # Maybe no overall image, maybe image selection happens at parts?
        # self.image_filename = info['image_filepath']

        super(JellySelectButton, self).__init__(**kwargs)

        try:
            # Create moving Jelly within button
            j = construct_creature(jelly_store, angle=90, phy_group_num=1)
            self.jelly = j
            self.ids.creature_widget.set_creature(j)

            # Loaded successfully, remove image
            # self.remove_widget(self.ids.image)

        except InsufficientData as ex:
            Logger.info("Not enough data to preview Jelly %s: %s", self.creature_id, ex.message)

        except:
            Logger.exception("Problem previewing Jelly %s within button", self.creature_id)
            # raise

    def on_release(self):
        # TODO long press to edit? Other options, delete, etc. Action Menu of JellyEditor?
        #print(self.last_touch)
        pass

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

# FIXME maybe remove, using SettingsItem
class TweakSetting(BoxLayout):
    """A Tweak with a label,
    TODO help info
    """
    # TODO highlight like setting does?

    title = StringProperty()
    help_text = StringProperty()
