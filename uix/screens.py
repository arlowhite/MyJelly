__author__ = 'awhite'

from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from uix.elements import JellySelectButton

class JellyEnvironmentScreen(Screen):
    """Living area for the Jelly where it moves around.
    Tap anywhere to pause and bring-up menu to take car of Jelly
    and get to other screens.
    """

class JellySelectionScreen(Screen):
    "Displays all user's Jellies and option to create new ones"

    def display_jellies(self, jelly_data):
        # TODO List adapter stuff
        grid = self.ids.jelly_grid
        for jdata in jelly_data:
            grid.add_widget(JellySelectButton(jdata))

class JellyAnimationConstructorScreen(Screen):
    "Modify the Mesh animation for the selected Jelly"

    def set_animation_data(self, data):
        ac = self.ids.animation_constructor
        ac.animation_data = data

    def restore_state(self):
        # Called if App resumed and this screen was open
        # Get last opened AnimationData

        pass


# FIXME Maybe always switch_to to clean-up memory
class JellyScreenManager(ScreenManager):
    "Choose transition animations based on screens"

    # Transition left to these
    main_screens = ['JellySelection', 'JellyEnvironment']

    to_main_transition = SlideTransition(direction='right')
    to_other_transition = SlideTransition(direction='left')

    def on_current(self, instance, value):
        # value is screen name
        # Decide transition based on name
        if value in JellyScreenManager.main_screens:
            self.transition = JellyScreenManager.to_main_transition
        else:
            self.transition = JellyScreenManager.to_other_transition

        super(JellyScreenManager, self).on_current(instance, value)

