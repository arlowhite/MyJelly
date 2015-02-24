__author__ = 'awhite'

import kivy
kivy.require('1.8.0')

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.clock import Clock

from kivy.graphics import Canvas, Color, Line
from kivy.vector import Vector

from visuals.creatures import Jelly
from visuals.anim_constructors import AnimationConstructor
from visuals.drawn_visual import Path, ControlPoint
#from behaviors.basic import FollowPath


class MyJellyGame(Widget):

    def __init__(self):
        super(MyJellyGame, self).__init__()

        self.started = False

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

        Clock.schedule_interval(self.clock_tick, 1/60.0)
        self.started = True

    def pause(self):
        Clock.unschedule(self.clock_tick)

    def on_done_pressed(self):
        # FIXME
        self.anim_constr.finalize_control_points()


class MyJellyApp(App):
    def build(self):
        game = MyJellyGame()

        return game

    def on_start(self):
        # FIXME Is this called on resume? Best place for this code
        # canvas.after instead?
        game = self.root


        jelly = Jelly()
        #jelly.center = game.center
        #jelly.pos = (200, 200)
        #center

        #size 1/2 window
        ac = AnimationConstructor(jelly)
        ac.pos = (50, 50)


        #self.add_ally(jelly)
        # TODO Better object organization
        game.anim_constr = ac
        game.jelly = jelly
        game.add_widget(ac)
        game.start()



if __name__ == '__main__':
    MyJellyApp().run()

# Loop?
# Everyone mooves, then check interactions