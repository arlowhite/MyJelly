__author__ = 'awhite'

import os.path as P
import random
from functools import partial

from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy.clock import Clock
from kivy.utils import platform
from kivy.logger import Logger, LOG_LEVELS
from kivy.properties import StringProperty, ObjectProperty, BooleanProperty
from kivy.animation import Animation
from kivy.uix.actionbar import ActionButton
from kivy.uix.settings import Settings

import cymunk as phy

from visuals.animations import setup_step
from visuals.creatures.jelly import JellyBell, GooeyBodyPart
from uix.elements import JellySelectButton, TweakSetting
from uix.environment import BasicEnvironment
from uix.animation_constructors import AnimationConstructor
from data.state_storage import load_jelly_storage, load_all_jellies, delete_jelly, \
    construct_creature, constructable_members, new_jelly, lookup_constructable

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

from kivy.uix.settings import SettingItem

class TweakSettingItem(SettingItem):
    """Tweak setting menu item
    """

class PartTweakScreen(Screen):
    """Lists the Tweak selection for a part
    """

    selected = ObjectProperty(None)

    @property
    def tweaks(self):
        return self.ids.tweaks_container.children

    def add_tweak(self, widget):
        tweaks_container = self.ids.tweaks_container
        widget.size_hint_y = None
        widget.size_hint_x = 1.0
        tweaks_container.add_widget(widget)
        widget.bind(on_release=self._child_on_release)

    def clear_tweaks(self, animate=True):
        tweaks_container = self.ids.tweaks_container

        if not tweaks_container.children:
            return

        tweaks_container.clear_widgets()

        # May get screwed up by on_size? but that probably won't be an issue
        # anim = Animation(x=tweaks_container.x - tweaks_container.width, duration=0.5)
        # for child in tweaks_container.children:
        #     anim.start(child)

    def _child_on_release(self, setting_item):
        self.selected = setting_item

class CreatureTweakScreen(AppScreen):
    """Shows creature moving behind screen with various tweaks to adjust the body parts
    """

    state_attributes = ('creature_id',)

    creature_id = StringProperty()
    selected = ObjectProperty(None)
    slider_grabbed = BooleanProperty(False)

    creature_turning = BooleanProperty(False)

    def __init__(self, **kwargs):
        self._initialized = False
        self.creature = None
        self.creature_store = None
        self.__adjusting_slider = False

        # Mapping of part_name to its tweaks dictionary in the store structure
        # value is tuple: (tweaks, tweaks_defaults, tweaks_meta)
        # keys entered by _create_tweaks_screen
        self._store_tweaks = {}
        # Mapping of part_name to its Constructor Class
        self._part_classes = {}

        super(CreatureTweakScreen, self).__init__(**kwargs)

    def on_size(self, _, size):
        if self.parent is None:
            # Ignore default size
            return

        if not self._initialized:
            self.initialize()

    def initialize(self):
        creature_id = self.creature_id
        self.creature_store = store = load_jelly_storage(creature_id)
        constrs = store['info']['creature_constructors']

        _store_tweaks = self._store_tweaks

        slider = self.ids.slider
        slider.bind(value=self.on_slider_value)

        # ActionGroup spinner
        tweaks_selector = self.ids.tweaks_part_selector

        for part_name in constrs:
            # FIXME instead add parts to menu and trigger on_select current part_name

            if part_name not in store:
                # part not edited yet
                # TODO maybe show entry with message that links back to construction
                continue

            part_store = store[part_name]
            part_class, constructor_path, _ = lookup_constructable(part_store)
            self._part_classes[part_name] = part_class

            button = ActionButton(text=part_class.part_title)
            button.bind(on_press=partial(self.display_part_tweaks, part_name))
            tweaks_selector.add_widget(button)


        self.display_part_tweaks(constrs[0])

        Clock.schedule_once(self._create_creature_env, 0)
        self._initialized = True

    def display_part_tweaks(self, part_name, button=None):
        """Display the tweaks screen for the specified part_name.
        Note: button supplied when called via on_press event
        """
        if button:
            part_selector = self.ids.tweaks_part_selector
            if part_selector._dropdown:
                part_selector._dropdown.dismiss()
            else:
                Logger.warning('%s: display_part_tweaks called with button, but no dropdown to dismiss.',
                               self.__class__.__name__)

        # Update the ActionGroup spinner text
        part_class = self._part_classes[part_name]
        self.ids.tweaks_part_selector.text = part_class.part_title

        sm = self.ids.tweaks_screen_manager
        if sm.has_screen(part_name):
            sm.current = part_name

        else:
            screen = self._create_tweaks_screen(part_name)
            sm.add_widget(screen)
            sm.current = part_name

    def _create_tweaks_screen(self, part_name):
        Logger.debug('Generating tweaks screen for part %s', part_name)

        part_store = self.creature_store[part_name]
        part_class = self._part_classes[part_name]
        constructor_path = part_class.class_path

        # Look for tweaks keywordarg in Constructor structure
        try:
            tweaks = part_store[constructor_path]['tweaks']
        except KeyError:
            tweaks = {}
            part_store[constructor_path]['tweaks'] = tweaks

        try:
            tweaks_meta = part_class.tweaks_meta
            tweaks_defaults = part_class.tweaks_defaults
        except AttributeError:
            Logger.exception('Unable to create Tweaks screen for part %s', part_name)
            raise

        self._store_tweaks[part_name] = (tweaks, tweaks_defaults, tweaks_meta)

        screen = PartTweakScreen(name=part_name)

        for tweak_name, options in tweaks_meta.viewitems():
            # 'push_factor': {'type': float, 'min': 0.05, 'max': 0.4, 'ui': 'Slider'}
            if options.ui != 'Slider':
                raise NotImplementedError('Only support Slider')

            # widget = TweakSetting(title=tweak_name)
            widget = TweakSettingItem(title=options.title, section=part_name, panel=self, key=tweak_name,
                                      desc=options.desc)

            widget.tweak_options = options
            screen.add_tweak(widget)

        screen.bind(selected=self.setter('selected'))
        return screen

    def _create_creature_env(self, dt):
        self.creature_env = env = BasicEnvironment()
        self.add_widget(env, len(self.children))

        # Wait until initialized so that creature can be centered in parent
        env.bind(initialized=self.reset_creature)

    def on_selected(self, _, setting_item):
        # Property ensures no duplicate calls for same menu item
        slider_opacity = 0.0 if setting_item is None else 1.0
        slider = self.ids.slider
        if slider_opacity != slider.opacity:
            Animation(opacity=slider_opacity).start(slider)

        if setting_item is None:
            return

        opts = setting_item.tweak_options
        # FIXME Assuming Slider
        value = setting_item.value
        if __debug__:
            Logger.debug('%s: on_selected %s setting Slider.value=%s', self.__class__.__name__,
                         setting_item.key, value)
        # min/max are old values, so must set them first otherwise they will adjust value if
        # it is outside range. However, changing min/max will also adjust current value in the same way, so need to
        # disable on_slider_value side-effects.
        self.__adjusting_slider = True
        try:
            # Set min, max, then value, otherwise value may be limited by Slider
            slider.min = opts.min
            slider.max = opts.max
            slider.value = value
        finally:
            self.__adjusting_slider = False

    def get_value(self, part_name, tweak_name):
        """SettingItems call panel.get_value"""

        # TODO think about this code design, this seems awkward...
        tweaks, tweaks_defaults, tweaks_meta = self._store_tweaks[part_name]

        try:
            value = tweaks[tweak_name]
        except KeyError:
            value = tweaks_defaults[tweak_name]

        Logger.debug('%s: get_value %s:%s=%s', self.__class__.__name__, part_name, tweak_name, value)
        return value

    def set_value(self, part_name, tweak_name, value):
        # Logger.debug('set_value %s:%s=%s', part_name, tweak_name, value)
        tweaks, tweaks_defaults, tweaks_meta = self._store_tweaks[part_name]
        value = tweaks_meta[tweak_name].type(value)

        # Update structure in store
        tweaks[tweak_name] = value

        if self.creature:
            self.creature.adjust_part_tweak(part_name, tweak_name, value)

    def save_state(self):
        if Logger.isEnabledFor(LOG_LEVELS['debug']):
            for part_name, tweak_data in self._store_tweaks.viewitems():
                tweaks = tweak_data[0]
                Logger.debug('%s: save_state() part_name=%s\n%s',
                             self.__class__.__name__, part_name, tweaks)

        self.creature_store.store_sync()

    # TODO Action menu item for each part

    def on_slider_value(self, _, value):
        if not self.__adjusting_slider:
            assert self.selected is not None
            self.selected.value = value

    def on_slider_grabbed(self, _, grabbed):
        if self.selected is None:
            return

        opacity = 0.0 if grabbed else 1.0

        sm = self.ids.tweaks_screen_manager
        selected = self.selected
        not_selected = [x for x in sm.current_screen.tweaks if x is not selected]
        for w in not_selected:
            Animation(opacity=opacity, duration=0.2).start(w)

    def on_touch_down(self, touch):
        super(self.__class__, self).on_touch_down(touch)

        # grab_list contains weakrefs
        if self.ids.slider in (x() for x in touch.grab_list):
            self.slider_grabbed = True

    def on_touch_up(self, touch):
        if self.ids.slider not in touch.grab_list:
            self.slider_grabbed = False

    def reset_creature(self, *args):
        # Just remove and create a new creature
        env = self.creature_env

        if self.creature:
            env.remove_creature(self.creature)

        creature_id = self.creature_id
        store = load_jelly_storage(creature_id)
        self.creature = creature = construct_creature(store, pos=env.center)
        creature.orient(0)
        env.add_creature(creature)

    def _creature_orient_update(self, dt):
        # update the creature to always orient left 89 degrees
        creature = self.creature
        creature.orient(creature.angle + 89)

    def on_creature_turning(self, _, turning):
        creature = self.creature
        print(turning)
        if turning:
            Clock.schedule_interval(self._creature_orient_update, 1/20.0)

        else:
            self.creature.orient(None)
            Clock.unschedule(self._creature_orient_update)
