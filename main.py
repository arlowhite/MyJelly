#!/usr/bin/env python

__author__ = 'awhite'
__version__ = '0.1'

import gettext
import inspect

# Localization setup
gettext.bindtextdomain('messages', 'locale')
gettext.textdomain('messages')
_ = gettext.lgettext

import kivy
kivy.require('1.9.1')

from kivy.config import Config
#Config.set('graphics', 'fullscreen', '0')
Config.set('kivy', 'log_level', 'debug')

from kivy.app import App
from kivy.logger import Logger
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.metrics import Metrics

#from behaviors.basic import FollowPath
from data import state_storage, constructable
from data.state_storage import load_app_storage, new_jelly
from uix import screens
from uix.elements import *
from uix.hacks_fixes import *

class MyJellyApp(App):
    def build(self):
        Logger.debug('dpi=%s', Metrics.dpi)

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

        screen_state = screen.get_state()
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
        if state:
            self.open_screen(name, **state)
        else:
            self.open_screen(name)

    # def on_start(self):
    #     # FIXME Is this called on resume? Best place for this code
    #     # canvas.after instead?
    #     game = self.root
    #
    #
    #     jelly = JellyBell()
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

    def open_screen(self, screen, **screen_args):
        # FIXME **kwargs make sure works in KV; then refactor
        "screen: instance or string, screen_state: dictionary"
        Logger.debug('Opening screen: %s {%s}', screen, screen_args)
        screen_class = screens.load(screen)

        if not issubclass(screen_class, Screen):
            raise ValueError('%s is not a Screen!'%screen)

        current_screen = self.screen_manager.current_screen

        try:
            s = screen_class(**screen_args) if screen_args else screen_class()
        except:
            Logger.exception('Failed to open_screen(%s, %s)'%(screen, screen_args))
            raise

        # TODO left/right decision, sort screens?
        self.screen_manager.switch_to(s)

if __name__ == '__main__':
    app = MyJellyApp()

    # Specify legal constructor classes
    for member in inspect.getmembers(constructable):
        if member[0].startswith('_'):
            continue

        clazz = member[1]
        path = '{}.{}'.format(clazz.__module__, clazz.__name__)
        state_storage.constructable_members[path] = clazz

    # Specify data storage directory
    # TODO better directory for android?
    state_storage.user_data_dir = app.user_data_dir

    app.run()
