__author__ = 'awhite'

import random
from types import TypeType

from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy.utils import platform
from kivy.logger import Logger
from kivy.properties import StringProperty, ObjectProperty
from kivy.uix.popup import Popup

from uix.elements import JellySelectButton
from uix.environment import BasicEnvironment
from data.state_storage import load_all_jellies, load_jelly_storage, delete_jelly, \
    construct_creature, new_jelly
from visuals.creatures.jelly import Parts
from misc.util import not_none_keywords

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

def import_photo_then(title, obj, **kwargs):
    """Show Import photo UI, then open screen or call callback if image selected.
    :param callable or string function will be called with image_filepath argument. A string is assumed to
    be a screen and will be opened with app.open_screen and image_filepath as a kwarg
    :param kwargs keyword arguments for screen names
    """
    assert callable(obj)
    app = App.get_running_app()

    # if isinstance(obj, TypeType):
    #     # Class of some kind, create a function that constructs it with kwargs
    #     def func(image_filepath):
    #         obj(image_filepath=image_filepath, **kwargs)
    #
    #     obj = func

    if isinstance(obj, basestring):
        def func(image_filepath):
            app.open_screen(obj, image_filepath=image_filepath, **kwargs)

        obj = func

    # Could do Popup, but just stick with the Screen scheme for now
    popup = ImportImagePopup(title=title, then=obj)
    popup.open()

# TODO select from previous creature images
# TODO select from images used in any creature
class ImportImagePopup(Popup):
    """Provides UI for importing a photo from the file system
    or TODO another creature/this creature
    """

    @not_none_keywords('then')
    def __init__(self, then=None, **kwargs):
        """
        :param title: Text to display to user that provides context
        :param then: callable to call with selected image_filepath
        """

        super(ImportImagePopup, self).__init__(**kwargs)
        self.then = then

    def on_import_gallery(self):
        self.dismiss()
        app = App.get_running_app()

        if platform == 'android':
            from misc import android_ui

            android_ui.user_select_image(self.then)

        else:
            app.open_screen('KivyImageSelectScreen', then=self.then)


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
            # Number of each Jelly species
            for x in range(1):
                Logger.debug('Creating Jelly %s', store.creature_id)
                # FIXME Random position code needs to verify width > margin
                #pos = random.randint(110, self.width - 110), random.randint(110, self.height - 110)
                pos = self.width/2.0, self.height/2.0
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
        """Create a new jelly and open the design screen.
        """
        creature_id = new_jelly()
        App.get_running_app().open_screen('JellyDesignScreen', creature_id=creature_id)


class JellyDesignScreen(AppScreen):
    """Provides UI to add new parts to a create and a selection of the created parts as well as
    access to creature tweaks
    """

    parts_layout = ObjectProperty(None)

    state_attributes = ('creature_id',)

    _screen_for_part = {
        Parts.jelly_bell: 'JellyBellConstructorScreen',
        Parts.gooey_body: 'AnimationConstructorScreen',
        Parts.tentacles_group: 'TentaclesConstructorScreen'
    }

    group_parts = (Parts.tentacles_group, )

    def __init__(self, **kwargs):
        self.creature_id = kwargs['creature_id']
        super(JellyDesignScreen, self).__init__(**kwargs)

        # Load list of existing parts
        # TODO in future cool visual part selection screen
        from kivy.uix.button import Button
        store = load_jelly_storage(self.creature_id)
        for part_instance_name in store.creature_constructors:
            # TODO labels?
            b = Button(text=part_instance_name, on_press=self.open_part_constructor)
            b.part_instance_name = part_instance_name
            self.parts_layout.add_widget(b)

    def screen_for_part(self, part_name):
        for name, screen_name in self._screen_for_part.viewitems():
            if part_name.startswith(name):
                return screen_name

        raise KeyError('No construction screen matches part name {}'.format(part_name))

    def delete_jelly(self):
        delete_jelly(self.creature_id)
        # TODO user popup message & undo option
        App.get_running_app().open_screen('JellySelectionScreen')

    def open_part_constructor(self, button):
        pin = button.part_instance_name
        screen_name = self.screen_for_part(pin)
        App.get_running_app().open_screen(screen_name, creature_id=self.creature_id, part_name=pin)

    def add_part(self, part_name):
        """Add the given part name (from Parts) to the creature.
        Opens import photo dialog as all parts start with an image.
        If the user selects an image, Creates a new group or part instance in the store
        and opens the appropriate part editor.
        """
        # Dismiss the ActionGroup or it will overlay the image selector
        action_group = self.ids.add_part_action_group
        # First two don't work. bug?
        # action_group.is_open = False
        # action_group._toggle_dropdown()
        action_group._dropdown.dismiss()

        cid = self.creature_id
        screen_for_part = self.screen_for_part
        group_parts = self.group_parts

        def callback(image_filepath):
            app = App.get_running_app()
            store = load_jelly_storage(cid)

            screen_name = screen_for_part(part_name)

            if part_name in group_parts:
                part_instance_name = store.new_group(part_name)
            else:
                part_instance_name = store.add_part(part_name)

            store.creature_constructors.append(part_instance_name)

            app.open_screen(screen_name, creature_id=cid, part_name=part_instance_name,
                            image_filepath=image_filepath)

        # part_name may actually be a group_name, but just make constructor screens use same kwarg
        import_photo_then('Select image for {}'.format(part_name), callback)
