__author__ = 'awhite'

import os.path as P
import random

from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.app import App
from kivy.clock import Clock
from kivy.utils import platform
from kivy.logger import Logger
from kivy.properties import StringProperty
from kivy.animation import Animation

import cymunk as phy

from visuals.animations import setup_step
from visuals.creatures.jelly import JellyBell, GooeyBodyPart
from uix.elements import JellySelectButton
from uix.animation_constructors import AnimationConstructor
from data.state_storage import load_jelly_storage, load_all_jellies, delete_jelly, \
    construct_creature, constructable_members, new_jelly
from misc.util import cleanup_space


constructor_class_for_part = {
    'jelly_bell': JellyBell,
    'tentacles': GooeyBodyPart
}

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

        # TODO different update intervals for physics/animations?
        self.update_interval = 1/60.0

    def on_size(self, _, size):
        if size == [1, 1]:
            return

        self.initialize()
        self.unbind(size=self.on_size)

    def initialize(self):
        "called after size set once"
        Logger.debug('%s: initialize()', self.__class__.__name__)

        # Setup physics space
        # TODO need to respond to resizes?
        # http://niko.in.ua/blog/using-physics-with-kivy/
        # kw - is some key-word arguments for configuting Space
        self.phy_space = space = phy.Space()
        # space.damping = 0.9

        # wall = phy.Segment(phy.Body(), (0, 1), (3000, 1), 0.0)
        # wall.friction = 0.8
        # space.add(wall)
        #
        # wall = phy.Segment(phy.Body(), (1, 3000), (1, 3000), 0.0)
        # wall.friction = 0.8
        # space.add(wall)

        jelly_num = 1
        for store in load_all_jellies():
            for x in range(1):
                Logger.debug('Creating Jelly %s', store['info']['id'])
                pos = random.randint(110, self.width-110), random.randint(110, self.height-110)
                # pos = self.width/2.0, self.height/2.0
                # angle = random.randint(-180, 180)
                angle = 90
                j = construct_creature(store, pos=pos, angle=angle, phy_group_num=jelly_num, parent=self)
                jelly_num += 1
                #j.speed = random.uniform(0, 10.0)
                # j.scale = random.uniform(0.75, 2.0)
                # j.scale = 0.5
                # j.change_angle(random.randint(-180, 180))
                # j.change_angle(0.0)
                # j.move(self.width/2., self.height/2.)
                # j.move(random.randint(110, self.width), random.randint(110, self.height))
                # print("Jelly pos=%s, angle=%s"%(j.pos, j.angle))
                # self.add_widget(j)
                self.canvas.add(j.canvas)  # TODO is this right?
                self.creatures.append(j)
                j.bind_environment(self)

            # break # FIXME remove

        Clock.schedule_interval(self.update_simulation, self.update_interval)
        # Clock.schedule_interval(self.change_behavior, 20)
        # self.change_behavior(0.0)


    def change_behavior(self, dt):
        # TODO Move angle changing code to Jelly
        for c in self.creatures:
            angle = c.angle + random.randint(-180, 180)
            print('change_behavior: current angle=%f  orienting %f deg'%(c.angle, angle))
            c.orient(angle)

    def update_simulation(self, dt):
        # Could pass dt, but docs state:
        # Update the space for the given time step. Using a fixed time step is
        # highly recommended. Doing so will increase the efficiency of the contact
        # persistence, requiring an order of magnitude fewer iterations to resolve
        # the collisions in the usual case.
        self.phy_space.step(self.update_interval)

        for c in self.creatures:
            c.update(dt)

    def pause(self):
        Logger.debug('{}: pause() unscheduling update_simulation'.format(self.__class__.__name__))
        Clock.unschedule(self.update_simulation)

    def on_leave(self):
        super(self.__class__, self).on_leave()
        Logger.debug('{}: on_leave() unscheduling update_simulation and cleaning-up physics space'
                     .format(self.__class__.__name__))

        Clock.unschedule(self.update_simulation)

        # Clean-up physics space
        cleanup_space(self.phy_space)

        # This seems to force garbage collection immediately
        self.phy_space = None

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


class JellyAnimationConstructorScreen(AppScreen):
    """Screen that for editing the Control Points of a Mesh.
    create a new screen instead of setting jelly_id or part_name for now"""
    state_attributes = ('jelly_id', 'animation_step', 'part_name')

    animation_step = StringProperty(setup_step)

    def __init__(self, **kwargs):
        # if 'jelly_id' not in kwargs:
            # raise ValueError('Must specify jelly_id')
        self.jelly_id = kwargs['jelly_id']
        # The animation name to store the data under in the store, may be configured in future
        self.part_name = kwargs['part_name']
        assert self.part_name != 'bell_animation'  # FIXME remove old name check, 2nd below
        self.animation_step = kwargs.get('animation_step', setup_step)

        store = load_jelly_storage(self.jelly_id)
        self.store = store

        super(JellyAnimationConstructorScreen, self).__init__(**kwargs)

        self.image_filepath = store['info']['image_filepath']  # TODO pass this into constructor?

        anim_const = self.ids.animation_constructor

        # Part classes know how to setup AnimationConstructor from JSON structure
        # Determine the part class and call setup_anim_constr()
        part_name = self.part_name
        try:
            part_structure = store[part_name]
            class_path = part_structure.keys()[0]
            constructable_members[class_path].setup_anim_constr(self, part_structure)

        except KeyError:
            # part was never edited before
            anim_const.image_filepath = self.image_filepath
            pass

        # Restore AnimationConstructor GUI state
        # FIXME Want to remember scale and pos even when opening Jelly fresh?
        try:
            anim_const.animate_changes = False
            anim_const.scale = kwargs['scatter_scale']  # must set scale before pos, otherwise pos changes
            anim_const.pos = kwargs['scatter_pos']
            anim_const.autosize = False  # prevent parent size change from changing pos/scale again

            self.ids.move_resize_switch.active = kwargs['move_resize']
            self.ids.animate_toggle.state = kwargs['animate_toggle_state']

        except KeyError as e:
            Logger.debug('%s: missing kwarg %s', self.__class__.__name__, e)

        finally:
            anim_const.animate_changes = True

        self.ids.animation_step_spinner.text_value = self.animation_step


    def on_animation_step(self, widget, step):
        Logger.debug('%s: on_animation_step %s', self.__class__.__name__, step)
        if step == setup_step:
            # Untoggle Animate button
            self.ids.animate_toggle.state = 'normal'

        self.ids.animation_constructor.animation_step = step

    def save_state(self):
        # After screen leaving animation ended
        # save animation data async
        ac = self.ids.animation_constructor
        store = self.store
        part_name = self.part_name

        # TODO Is this the appropriate place to hard-code this?
        # Probably refactor body part constructor GUI in reef game
        creature_constructors = store['info']['creature_constructors']

        assert part_name != 'bell_animation'  # FIXME remove this old name check
        # Current design expects part name to be added to creature_constructors first
        # (Indicating new part is avaliable for editing by user)
        assert part_name in creature_constructors
        constructor_class = constructor_class_for_part[part_name]
        store[part_name] = constructor_class.create_construction_structure(self)

        Logger.debug('{}: save_state() "{}" {}'
                     .format(self.__class__.__name__, part_name, store[part_name]))

        store.store_sync()


    def get_state(self):
        d = super(JellyAnimationConstructorScreen, self).get_state()

        ac = self.ids.animation_constructor
        d.update(dict(scatter_pos=ac.pos, scatter_scale=ac.scale,
                      move_resize=ac.move_resize,
                      animate_toggle_state=self.ids.animate_toggle.state))
        return d


class NewJellyScreen(AppScreen):
    "Screen for selecting an image that creates a new jelly"

    def __init__(self, **kwargs):
        super(NewJellyScreen, self).__init__(**kwargs)

        fc = self.ids.filechooser

        # TODO if os is android/linux/etc
        if platform=='android':
            # TODO is /sdcard standard across all android?
            fc.path = '/sdcard'

        else:
            home = P.expanduser('~')
            # Don't allow navigating above home
            # Seems like an unecessary limitation...
            # fc.rootpath = home

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
        jelly_id = new_jelly(filepath)

        App.get_running_app().open_screen('JellyDesignScreen', dict(jelly_id=jelly_id))
