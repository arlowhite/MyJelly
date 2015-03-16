__author__ = 'awhite'

import kivy
kivy.require('1.9.0')

#from kivy.config import Config
#Config.set('graphics', 'fullscreen', '0')

from kivy.app import App
from kivy.logger import Logger
from kivy.uix.widget import Widget
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock

#from behaviors.basic import FollowPath
from data.state_storage import load_app_storage
from uix import screens
from uix.elements import *
from uix.hacks_fixes import *
from uix.animation_constructors import AnimationConstructor


class MyJellyGame(Widget):

    def __init__(self):
        super(MyJellyGame, self).__init__()

        self.started = False

        self.pressed_once = False

    def clock_tick(self, dt):
        self.jelly.update_creature()

# Moved to Jelly class
    # def on_touch_down(self, touch):
    #     x, y = touch.x, touch.y
    #
    #     handled = super(MyJellyGame, self).on_touch_down(touch)
    #     if not handled:
    #         ctrl_pt = ControlPoint()
    #         ctrl_pt.center = (x,y)
    #         self.add_widget(ctrl_pt)
    #         return True
    #
    #     else:
    #         # Should be False
    #         return handled


    # FIXME Read about resume/start builtin
    def start(self):
        if self.started:
            return

        #Clock.schedule_interval(self.clock_tick, 1/60.0)
        self.started = True

    def pause(self):
        Clock.unschedule(self.clock_tick)

    def on_done_pressed(self):

        if not self.pressed_once:
            self.anim_constr.finalize_control_points()

        else:
            self.anim_constr.finalize_point_destinations()

            self.jelly.animate_bell()

        self.pressed_once = True


class MyJellyApp(App):
    def build(self):
        sm = ScreenManager()
        self.screen_manager = sm  # Could use root, but this is more clear

        try:
            self.restore_state()

        except:
            Logger.exception('Restoring app state failed')
            self.open_screen('JellySelectionScreen')

        #self.open_animation_constructor()
        Logger.debug('user_data_directory: %s', self.user_data_dir)

        return sm

    def on_pause(self):
        # try:
        Logger.debug('PAUSE, return True')
        # self.screen_manager.current_screen.on_pauseeaou()
        self.save_state()
        # Return True to indicate support pause
        # OpenGL is kept
        return True

        # except:
        # return False

    def on_stop(self):
        # Called in Linux when closing window
        self.save_state()


    def save_state(self):
        store = load_app_storage()
        screen = self.screen_manager.current_screen

        screen_state = screen.get_state() if hasattr(screen, 'get_state') else None
        state = {'class_name': self.screen_manager.current_screen.__class__.__name__,
                 'state': screen_state}

        Logger.debug('main: save_state() %s', state)
        store['screen'] = state
        store.store_sync()


    # def on_resume(self):
    #     Logger.debug('RESUME')
    #     storage.get
    #
    #     get('open_screen')
    #     #create screen
    #     screen_state = get('screen_state')
    #     screen.restore_state(screen_state)
    #
    # def _store_state(self):
    #     state_storage.put('open_screen', self.screen_manager.current)
    #     'screen_state'

    def restore_state(self):
        store = load_app_storage()
        screen = store['screen']
        name = screen['class_name']
        state = screen['state']
        Logger.info('main: restore_state, open_screen(%s, %s)'%(name, state))
        self.open_screen(name, state)


    # def on_start(self):
    #     # FIXME Is this called on resume? Best place for this code
    #     # canvas.after instead?
    #     game = self.root
    #
    #
    #     jelly = Jelly()
    #     #jelly.center = game.center
    #     #jelly.pos = (200, 200)
    #     #center
    #
    #     #size 1/2 window
    #     ac = AnimationConstructor(jelly)
    #     ac.pos = (50, 50)
    #
    #
    #     #self.add_ally(jelly)
    #     # TODO Better object organization
    #     game.anim_constr = ac
    #     game.jelly = jelly
    #     game.add_widget(ac)
    #     game.start()

    def open_screen(self, screen, screen_args = None):
        "screen: instance or string, screen_state: dictionary"
        Logger.debug('Opening screen: %s', screen)
        screen_class = screens.__dict__[screen]
        if not issubclass(screen_class, Screen):
            raise ValueError('%s is not a Screen!'%screen)

        s = screen_class(**screen_args) if screen_args else screen_class()
        # TODO left/right decision, sort screens?
        self.screen_manager.switch_to(s)

    # def open_animation_constructor(self, jelly=None):
    #     sm = self.screen_manager
    #     # if not sm.has_screen('JellyAnimationConstructor'):
    #     # s = JellyAnimationConstructorScreen(name='JellyAnimationConstructor')
    #         # sm.add_widget(s)
    #
    #     # sm.current = 'JellyAnimationConstructor'
    #     # switch_to destroys old screen
    #     s = JellyAnimationConstructorScreen(name='JellyAnimationConstructor')
    #     s.set_animation_data(jelly)
    #     sm.switch_to(s, direction='left')
    #     #ac = sm.current_screen
    #
    #
    # def open_jelly_selection(self):
    #     selection = JellySelectionScreen(name="JellySelection")
    #     # # FIXME Hardcoded, load from local storage
    #     holland = JellyData()
    #     holland.bell_image_filename = 'media/images/holland_jelly.png'
    #     data = [JellyData(), holland, JellyData()]
    #     selection.display_jellies(data)
    #
    #     self.screen_manager.switch_to(selection, direction='right')
    #     #self.screen_manager.add_widget(selection)
    #
    # def open_jelly_environment(self):
    #     # Hackish, check if AnimationConstructor screen, grab Jelly Data?
    #
    #     pass





if __name__ == '__main__':
    MyJellyApp().run()

