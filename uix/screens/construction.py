__author__ = 'awhite'

import os.path as P
from functools import partial

from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy.clock import Clock
from kivy.utils import platform
from kivy.logger import Logger, LOG_LEVELS
from kivy.properties import StringProperty, ObjectProperty, BooleanProperty, BoundedNumericProperty, \
    ListProperty
from kivy.animation import Animation
from kivy.uix.actionbar import ActionButton

from .main_screens import AppScreen
from visuals.animations import setup_step
from visuals.creatures.jelly import JellyBell, GooeyBodyPart, Tentacle, Parts
from uix.environment import BasicEnvironment
from uix.elements import LabeledSpinner
from uix.animation_constructors import AnimationConstructor
from data.state_storage import load_jelly_storage, \
    construct_creature, constructable_members, new_jelly, lookup_constructable
from misc.util import not_none_keywords

# Map Parts part_names to their constructors
_parts_to_constructors = {
    Parts.jelly_bell: JellyBell,
    Parts.gooey_body: GooeyBodyPart,
    Parts.tentacles_group: Tentacle
}
def constructor_class_for_part(name):
    for part_base, constr in _parts_to_constructors.viewitems():
        if name.startswith(part_base):
            return constr

    raise KeyError('No constructor match for part name {}'.format(name))


class AnimationConstructorScreen(AppScreen):
    """Screen that for editing the Control Points of a Mesh.
    Provides UI to switch between animation_steps if set."""
    state_attributes = ('creature_id', 'animation_step', 'part_name')

    animation_step = StringProperty(setup_step)
    # Selectable Animation Steps [(value, label), ...]
    animation_steps = ListProperty()

    def __init__(self, image_filepath=None, **kwargs):
        # if 'creature_id' not in kwargs:
            # raise ValueError('Must specify creature_id')
        self.creature_id = kwargs['creature_id']
        # The animation name to store the data under in the store, may be configured in future
        self.part_name = kwargs['part_name']
        self.store = store = load_jelly_storage(self.creature_id)
        self.__animation_step_spinner = None

        super(AnimationConstructorScreen, self).__init__(**kwargs)

        # self.image_filepath is set from store if exists there, otherwise must be provided
        self.image_filepath = image_filepath  # may be None right now

        # TODO Kivy docs recommend using a property instead of ids?
        anim_const = self.ids.animation_constructor
        assert isinstance(anim_const, AnimationConstructor)

        # Part classes know how to setup AnimationConstructor from JSON structure
        # Determine the part class and call setup_anim_constr()
        # Note: this is actually a part_instance_name
        part_name = self.part_name
        class_path = None
        try:
            part_structure = store[part_name]
            class_path = part_structure.keys()[0]
        except (KeyError, IndexError):
            # part was never edited before
            if self.image_filepath is None:
                raise AssertionError('part store is missing, but not provided image_filepath!')

            anim_const.image_filepath = self.image_filepath

        if class_path:
            constructable_members[class_path].setup_anim_constr(self, part_structure)
            assert self.image_filepath

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
            # This is expected when not restoring screen state
            Logger.debug('%s: fresh screen (missing kwarg %s)',
                         self.__class__.__name__, e)

        finally:
            anim_const.animate_changes = True

        # Must bind manually because on_PROP is called before widget built
        # (These properties need Build to finish first)
        # This animates when not wanted...
        with anim_const:
            self.on_animation_step_change(self, self.animation_step)

        self.bind(animation_step=self.on_animation_step_change)

    def on_animation_step_change(self, widget, step):
        Logger.debug('%s: on_animation_step %s', self.__class__.__name__, step)
        if step == setup_step:
            # Untoggle Animate button
            self.ids.animate_toggle.state = 'normal'

        ac = self.ids.animation_constructor
        ac.animation_step = step

    def on_animation_steps(self, widget, steps):
        spinner = self.__animation_step_spinner
        if not spinner:
            self.__animation_step_spinner = spinner = LabeledSpinner(
                size_hint=(0.8, None), pos_hint={'center_x': 0.5}, height='40sp')

            # spinner.bind(texture_size=spinner.setter('size'))
            spinner.bind(text_value=self.setter('animation_step'))

        spinner.values = [x[1] for x in steps]
        spinner.text_values = [x[0] for x in steps]
        layout = self.ids.main_layout
        layout.add_widget(spinner, 2)

        if self.animation_step in spinner.text_values:
            spinner.text_value = self.animation_step
        else:
            Logger.warning('%s is not in text_values, defaulting', self.animation_step)
            spinner.text_value = spinner.text_values[0]

    def save_state(self):
        # After screen leaving animation ended
        # save animation data async
        ac = self.ids.animation_constructor
        store = self.store
        part_name = self.part_name

        # TODO Is this the appropriate place to hard-code this?
        # Probably refactor body part constructor GUI in reef game
        creature_constructors = store.creature_constructors

        # Current design expects part name to be added to creature_constructors first
        # (Indicating new part is avaliable for editing by user)
        assert part_name in creature_constructors
        constructor_class = constructor_class_for_part(part_name)

        # The part in the store may have structure set by other components, such as tweaks
        # So this code should merge some parts rather than overwrite
        # But are there cases where structure should be overwritten? How to determine each?

        # For example, will something modify MeshAnimator kwargs?
        # Would be cleaner and safer to have this GUI set those.

        # For now KIS and just pull out tweaks and insert it again.
        tweaks = None
        try:
            tweaks = store[part_name][constructor_class.class_path]['tweaks']
        except KeyError:
            # tweaks not set or class_path not set
            pass

        store[part_name] = constructor_class.create_construction_structure(self)
        if tweaks:
            # Make sure this code didn't add tweaks, in which case merging is necessary
            assert 'tweaks' not in store[part_name][constructor_class.class_path]
            store[part_name][constructor_class.class_path]['tweaks'] = tweaks

        Logger.debug('{}: save_state() "{}" {}'
                     .format(self.__class__.__name__, part_name, store[part_name]))

        store.store_sync()

    def get_state(self):
        d = super(AnimationConstructorScreen, self).get_state()

        ac = self.ids.animation_constructor
        d.update(dict(scatter_pos=ac.pos, scatter_scale=ac.scale,
                      move_resize=ac.move_resize,
                      animate_toggle_state=self.ids.animate_toggle.state))
        return d

class JellyBellConstructorScreen(AnimationConstructorScreen):

    def __init__(self, **kwargs):
        super(JellyBellConstructorScreen, self).__init__(**kwargs)
        self.animation_steps = zip(('__setup__', 'open_bell', 'closed_bell'),
                                   ('Setup', 'Open bell', 'Closed bell'))


class TentaclesConstructorScreen(AppScreen):
    """UI for defining a Tentacle and its instances.

    Drag out more tentacle copies, stretch
    Trash drag button
    """
    # FIXME
    pass

# FIXME save?


# TODO maybe native linux selector and other OSes too
# FIXME This screen cannot save state because of then
class KivyImageSelectScreen(AppScreen):
    "Screen for selecting an image that creates a new jelly"

    @not_none_keywords('then')
    def __init__(self, then=None, **kwargs):
        super(KivyImageSelectScreen, self).__init__(**kwargs)

        fc = self.ids.filechooser
        if not callable(then):
            raise ValueError('then is not callable')

        self.then = then

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
            Logger.warning('{}: selection with {} files'.format(self.__class__.__name__, len(files)))
            return

        filepath = files[0]
        self.then(filepath)

from kivy.uix.settings import SettingItem

class TweakSettingItem(SettingItem):
    """Tweak setting menu item
    """

class PartTweakScreen(Screen):
    """Lists the Tweak selection for a part
    """

    selected = ObjectProperty(None, allownone=True)

    @property
    def tweaks(self):
        return self.ids.tweaks_container.children

    def add_tweak(self, widget):
        tweaks_container = self.ids.tweaks_container
        widget.size_hint_y = None
        widget.size_hint_x = 1.0
        tweaks_container.add_widget(widget)
        widget.bind(on_release=self._child_on_release)

    def select_tweak(self, tweak_name):
        for child in self.ids.tweaks_container.children:
            if child.key == tweak_name:
                self.selected = child
                return

        raise ValueError("no tweak with name '%s'")

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
        if self.selected is None:
            self.selected = setting_item
        else:
            # Clicking item again unsets selected
            self.selected = None

    def on_selected(self, o, selected):
        """Move the selected item to the top of the screen and fade-out others
        Moves the screen itself. Changing current screen will reset.
        """
        scroll_view = self.ids.scroll_view
        tweaks_container = self.ids.tweaks_container  # GridLayout
        # change scroll_y (0.0 - 1.0)
        # or change content size

        show_list = selected is None
        Logger.debug('%s: on_selected %s  show_list=%s', self.__class__.__name__, selected, show_list)

        # Disable user from scrolling
        scroll_view.do_scroll_y = show_list

        # Fade-out other tweaks
        opacity = 1.0 if show_list else 0.0
        anim = Animation(opacity=opacity, duration=0.4)
        for child in tweaks_container.children:
            if child is not selected:
                child.disabled = not show_list
                anim.start(child)

        if selected:
            target_y = self._calc_y_for_item_top()
        else:
            target_y = 0

            # sine or quad
        Animation(y=target_y, duration=0.4, t='in_out_quad').start(self)

    def on_size(self, o, size):
        if self.selected:
            Animation.stop_all(self, 'y')
            # Let layouts settle before doing this
            # Binding tweaks_container size didn't work any better
            Clock.schedule_once(self._update_item_top, 0)

    def _update_item_top(self, dt):
        """Update y value so that selected item is at top"""
        self.y = self._calc_y_for_item_top()

    def _calc_y_for_item_top(self):
        """Calculate self.y value needed so that the selected item is at the top
        returns 0 and logs warning if nothing selected
        """
        selected = self.selected
        if selected is None:
            Logger.warning("%s: _calc_y_for_item_top called despite no item selected", self.__class__.__name__)
            return 0

        item_top = selected.to_window(selected.x, selected.top)[1]
        # screen_top = self.to_window(self.x, self.top)[1]
        parent = self.parent
        screen_top = parent.to_window(parent.x, parent.top)[1]
        target_y = self.y + screen_top - item_top
        return target_y


# TODO highlight selected part, pulse?
class CreatureTweakScreen(AppScreen):
    """Shows creature moving behind screen with various tweaks to adjust the body parts
    """

    state_attributes = ('creature_id', 'displayed_part_name', 'selected_tweak_name')

    creature_id = StringProperty()
    selected = ObjectProperty(None, allownone=True)
    displayed_part_name = StringProperty(None)
    selected_tweak_name = StringProperty(None, allownone=True)
    slider_grabbed = BooleanProperty(False)  # not used presently, but may be useful
    debug_visuals = BooleanProperty(False)
    obscure_color_alpha = BoundedNumericProperty(0.4, min=0.0, max=1.0)

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
        constrs = store.creature_constructors

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

        part_name = self.displayed_part_name
        self.display_part_tweaks(part_name if part_name else constrs[0])

        if self.selected_tweak_name:
            self.ids.tweaks_screen_manager.current_screen.select_tweak(self.selected_tweak_name)

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
        if sm.current_screen:
            sm.current_screen.selected = None

        if sm.has_screen(part_name):
            sm.current = part_name

        else:
            screen = self._create_tweaks_screen(part_name)
            sm.add_widget(screen)
            sm.current = part_name

        self.displayed_part_name = part_name

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

    def on_debug_visuals(self, o, debug):
        # Not worth making debug_visuals dynamic, just create a new creature
        self.reset_creature()

    def on_selected(self, _, setting_item):
        # Property ensures no duplicate calls for same menu item
        slider_opacity = 0.0 if setting_item is None else 1.0
        slider = self.ids.slider
        slider.disabled = setting_item is None
        if slider_opacity != slider.opacity:
            Animation(opacity=slider_opacity).start(slider)

        Animation(obscure_color_alpha=0.0 if setting_item else 0.4, duration=0.3, t='in_out_quad').start(self)

        if setting_item is None:
            self.selected_tweak_name = None
            return

        # Set Slider value, min, max for not None setting_item
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

        self.selected_tweak_name = setting_item.key

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
        self.creature = creature = construct_creature(store, pos=env.center, debug_visuals=self.debug_visuals)
        creature.orient(0)
        env.add_creature(creature)

    def _creature_orient_update(self, dt):
        # update the creature to always orient left 89 degrees
        creature = self.creature
        creature.orient(creature.angle + 89)

    def on_creature_turning(self, _, turning):
        creature = self.creature
        # FIXME follow-up on turning code
        print(turning)
        if turning:
            Clock.schedule_interval(self._creature_orient_update, 1/20.0)

        else:
            self.creature.orient(None)
            Clock.unschedule(self._creature_orient_update)

