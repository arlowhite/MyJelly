__author__ = 'awhite'

import random

from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy.utils import platform
from kivy.logger import Logger

from uix.elements import JellySelectButton
from uix.environment import BasicEnvironment
from data.state_storage import load_all_jellies, delete_jelly, \
    construct_creature, new_jelly

class AppScreen(Screen):
    """Provides state capturing methods and calls destroy on child widgets with
    destroy() method

    If Screens have state to manage and store themselves, they should do it in save_state()
    Screens should check the state they saved in the constructor.
    """

    def get_state(self):
        """Returns a dict of state_attributes that can be passed to the Screen's
        constructor to establish the same state in the future.

        Also calls save_state() if present

        returns None if no state_attributes
        """

        if hasattr(self, 'save_state'):
            self.save_state()

        if not hasattr(self.__class__, 'state_attributes'):
            return None

        d = {}
        for attr in self.__class__.state_attributes:
            d[attr] = getattr(self, attr)

        return d

    def on_leave(self):
        if hasattr(self, 'save_state'):
            self.save_state()

        # Check for widgets with destroy methods
        for widget in self.walk(restrict=True):
            if hasattr(widget, 'destroy'):
                widget.destroy()

        # We always switch_to, which destroys old screens
        self.clear_widgets()

class JellyEnvironmentScreen(AppScreen):
    """Living area for the Jelly where it moves around.
    Tap anywhere to pause and bring-up menu to take car of Jelly
    and get to other screens.
    """
    # FIXME for now we're crazy and showing all Jellies

    def __init__(self, **kwargs):
        self.creatures = []
        super(JellyEnvironmentScreen, self).__init__(**kwargs)

        self.creature_env = env = BasicEnvironment()
        env.bind(initialized=self.create_creatures)
        self.add_widget(env)

    def create_creatures(self, _, initialized):
        creature_env = self.creature_env

        jelly_num = 1
        for store in load_all_jellies():
            for x in range(1):
                Logger.debug('Creating Jelly %s', store['info']['id'])
                pos = random.randint(110, self.width - 110), random.randint(110, self.height - 110)
                # pos = self.width/2.0, self.height/2.0
                # angle = random.randint(-180, 180)
                angle = 90
                j = construct_creature(store, pos=pos, angle=angle, phy_group_num=jelly_num)
                jelly_num += 1
                # j.speed = random.uniform(0, 10.0)
                # j.scale = random.uniform(0.75, 2.0)
                # j.scale = 0.5
                # j.change_angle(random.randint(-180, 180))
                # j.change_angle(0.0)
                # j.move(self.width/2., self.height/2.)
                # j.move(random.randint(110, self.width), random.randint(110, self.height))
                # print("Jelly pos=%s, angle=%s"%(j.pos, j.angle))
                # self.add_widget(j)
                creature_env.add_creature(j)

    # FIXME Did I bind App to this?
    def pause(self):
        Logger.debug('{}: pause() unscheduling update_simulation'.format(self.__class__.__name__))
        self.creature_env.paused = True

    # TODO def resume

    # TODO UI for leaving Environment screen
    def on_touch_down(self, touch):
        App.get_running_app().open_screen('JellySelectionScreen')



class JellySelectionScreen(AppScreen):
    "Displays all user's Jellies and option to create new ones"

    def __init__(self, **kwargs):
        super(JellySelectionScreen, self).__init__(**kwargs)

        self.display_jellies(load_all_jellies())

    def display_jellies(self, jelly_stores):
        # TODO List adapter stuff
        # TODO StackLayout instead?
        grid = self.ids.jelly_grid
        for jdata in jelly_stores:
            grid.add_widget(JellySelectButton(jdata))

    def new_jelly(self):
        """Launch the UI for the user to create a new jelly from a selected image.
        On Android, uses native gallery picker Intent
        """
        app = App.get_running_app()

        if platform == 'android':
            from misc import android_ui

            android_ui.user_select_image(self.new_jelly_with_image)

        else:
            app.open_screen('NewJellyScreen')

    def new_jelly_with_image(self, image_filepath):
        """"""

        if image_filepath is None:
            # Nothing to do if user canceled selection
            return

        jelly_id = new_jelly(image_filepath)
        App.get_running_app().open_screen('JellyDesignScreen', dict(jelly_id=jelly_id))


class JellyDesignScreen(AppScreen):
    # menu to Bell, Tentacles, etc

    state_attributes = ('jelly_id',)

    def __init__(self, **kwargs):
        self.jelly_id = kwargs['jelly_id']
        super(JellyDesignScreen, self).__init__(**kwargs)

    def delete_jelly(self):
        delete_jelly(self.jelly_id)
        # TODO user popup message & undo option
        App.get_running_app().open_screen('JellySelectionScreen')


