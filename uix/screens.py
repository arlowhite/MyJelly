__author__ = 'awhite'

import os.path as P
import uuid

from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.app import App
from kivy.utils import platform
from kivy.logger import Logger
from kivy.properties import StringProperty

from visuals.animations import setup_step
from uix.elements import JellySelectButton
from uix.animation_constructors import AnimationConstructor

from data.state_storage import load_jelly_storage, load_all_jellies

class JellyEnvironmentScreen(Screen):
    """Living area for the Jelly where it moves around.
    Tap anywhere to pause and bring-up menu to take car of Jelly
    and get to other screens.
    """

class JellySelectionScreen(Screen):
    "Displays all user's Jellies and option to create new ones"

    def __init__(self, **kwargs):
        super(JellySelectionScreen, self).__init__(**kwargs)

        self.display_jellies(load_all_jellies())

    def display_jellies(self, jelly_stores):
        # TODO List adapter stuff
        # TODO StackLayout instead?
        grid = self.ids.jelly_grid
        for jdata in jelly_stores:
            info = jdata['info']
            grid.add_widget(JellySelectButton(info['id'], info['image_filepath']))

class JellyAnimationConstructorScreen(Screen):
    """Modify the Mesh animation for the selected Jelly.
    create a new screen instead of setting jelly_id or animation_name for now"""

    animation_step = StringProperty(setup_step)

    def __init__(self, **kwargs):
        # if 'jelly_id' not in kwargs:
            # raise ValueError('Must specify jelly_id')
        self.jelly_id = kwargs['jelly_id']
        # The animation name to store the data under in the store, may be configured in future
        self.animation_name = kwargs.get('animation_name', 'bell_animation')
        self.animation_step = kwargs.get('animation_step', setup_step)

        store = load_jelly_storage(self.jelly_id)
        self.store = store

        super(JellyAnimationConstructorScreen, self).__init__(**kwargs)

        anim_const = self.ids.animation_constructor
        if self.animation_name not in store:
            # In future may have different images for creature, and want to store all needed info under animation data
            store[self.animation_name] = {'image_filepath': store['info']['image_filepath']}

        anim_const.set_animation_data(store[self.animation_name], animation_step=self.animation_step)
        try:
            anim_const.animate_changes = False
            anim_const.scale = kwargs['scatter_scale']  # must set scale before pos, otherwise pos changes
            anim_const.pos = kwargs['scatter_pos']
            anim_const.autosize = False  # prevent parent size change from changing pos/scale again

            self.ids.move_resize_switch.active = kwargs['move_resize']
            self.ids.animate_toggle.state = kwargs['animate_toggle_state']
            anim_const.animate_changes = True

        except KeyError:
            pass

        self.ids.animation_step_spinner.text_value = self.animation_step


    def on_animation_step(self, widget, step):
        Logger.debug('%s: on_animation_step %s', self.__class__.__name__, step)
        if step == setup_step:
            # Untoggle Animate button
            self.ids.animate_toggle.state = 'normal'

        self.ids.animation_constructor.animation_step = step


    def on_leave(self, *args):
        # After screen leaving animation ended
        # save animation data async
        # animation_name could change in future?
        ac = self.ids.animation_constructor
        data = ac.get_animation_data()
        Logger.debug('JellyAnimationConstructorScreen: saving animation %s', data)
        self.store[self.animation_name] = data
        self.store.store_sync()

    def get_state(self):
        # Jelly state is stored separately
        self.on_leave()

        ac = self.ids.animation_constructor
        return dict(jelly_id=self.jelly_id, animation_step=self.animation_step,
                    scatter_pos=ac.pos, scatter_scale=ac.scale,
                    move_resize=ac.move_resize,
                    animate_toggle_state=self.ids.animate_toggle.state)


class NewJellyScreen(Screen):

    def __init__(self, **kwargs):
        super(NewJellyScreen, self).__init__(**kwargs)

        # TODO if os is android/linux/etc
        # if platform=='android'
        fc = self.ids.filechooser
        home = P.expanduser('~')
        # Don't allow navigating above home
        fc.rootpath = home

        p = P.join(home, 'Pictures')
        if P.isdir(p):
            fc.path = p
        else:
            fc.path = home

        fc.bind(selection=self.on_selection)



    def on_selection(self, filechooser, files):
        # No multi-select
        if len(files) != 1:
            Logger.warning('NewJellyScreen: selection with %d files'%len(files))
            return

        filepath = files[0]
        # TODO If image used before, ask if want to open that Jelly
        # TODO Copy image file for safe keeping?
        # TODO check if image file
        jelly_id = uuid.uuid4().hex
        jelly = load_jelly_storage(jelly_id)
        jelly.put('info', id=jelly_id, image_filepath = filepath)
        jelly.store_sync()  # As soon as image is saved, save jelly state

        App.get_running_app().open_screen('JellyAnimationConstructorScreen', dict(jelly_id=jelly_id))
