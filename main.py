__author__ = 'awhite'

import kivy
kivy.require('1.8.0')

from kivy.config import Config
Config.set('graphics', 'fullscreen', '0')

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.clock import Clock

#from behaviors.basic import FollowPath

from uix.screens import *
from uix.elements import *
from visuals.anim_constructors import AnimationConstructor

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
        sm = JellyScreenManager()
        self.screen_manager = sm  # Could use root, but this is more clear

        # # TODO show env if has Jelly
        # selection = JellySelectionScreen(name="JellySelection")
        # # FIXME Hardcoded, load from local storage
        # selection.display_jellies([JellyData()])
        # sm.add_widget(selection)

        self.open_animation_constructor()

        return sm

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

    def open_animation_constructor(self, jelly=None):
        sm = self.screen_manager
        if not sm.has_screen('JellyAnimationConstructor'):
            s = JellyAnimationConstructorScreen(name = 'JellyAnimationConstructor')
            sm.add_widget(s)

        sm.current = 'JellyAnimationConstructor'
        # switch_to destroys old screen
        #sm.switch_to(s, direction='left')
        ac = sm.current_screen
        ac.set_jelly_data(JellyData())





if __name__ == '__main__':
    MyJellyApp().run()

