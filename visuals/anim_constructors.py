__author__ = 'awhite'

#from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.widget import Widget
from kivy.graphics import Translate, Rectangle

from .drawn_visual import ControlPoint

# RelativeLayout or Scatter seems overcomplicated and causes issues
# just do it myself, don't really need to add_widget()
# TODO Padding so can pickup ControlPoint on edge


class AnimationConstructor(Widget):

    def __init__(self, widget, **kwargs):
        if not hasattr(widget, 'mesh'):
            raise ValueError('Widget has no Mesh to operate on')

        super(AnimationConstructor, self).__init__(**kwargs)

        with self.canvas.before:
            self._trans = Translate(xy = self.pos)

        self.ctrl_points = []

        self.widget = widget
        self.size = widget.size
        self.add_widget(widget)

        with self.canvas.before:
            Rectangle(size=self.size)

    def on_pos(self, widget, pos):
        self._trans.xy = pos


    def finalize_control_points(self):
        # Add averaged point
        # TODO consider whether user needs the ability to move it
        # Generate vertices

        x_mean = 0
        y_mean = 0
        for pt in self.ctrl_points:
            x_mean += pt.center_x
            y_mean += pt.center_y

        x_mean /= len(self.ctrl_points)
        y_mean /= len(self.ctrl_points)

        # Lock point to mesh...
        self.ctrl_points[0].get_vertice_coords()

    # From RelativeLayout, maybe make SimpleRelativeLayout?
    def to_local(self, x, y, **k):
        return x - self.x, y - self.y

    def on_touch_down(self, touch):
        x, y = touch.x, touch.y

        # Other Widgets, e.g. Button need us to return False to work
        if not self.collide_point(x, y):
            # Don't care up clicks outside self
            return False

        touch.push()
        touch.apply_transform_2d(self.to_local)
        handled = super(AnimationConstructor, self).on_touch_down(touch)

        if not handled:
            # TODO Edit mode config?
            # Create a new ControlPoint
            ctrl_pt = ControlPoint()

            #ctrl_pt.center = self.to_widget(x, y, relative=True)
            # Use transformed coordinates
            ctrl_pt.center = (touch.x, touch.y)
            self.add_widget(ctrl_pt)
            # TODO Create ControlPoint container of some kind
            self.ctrl_points.append(ctrl_pt)
            return True

        touch.pop()
        return handled

    def on_touch_move(self, touch):
        x, y = touch.x, touch.y
        touch.push()
        touch.apply_transform_2d(self.to_local)
        ret = super(AnimationConstructor, self).on_touch_move(touch)
        touch.pop()
        return ret

    def on_touch_up(self, touch):
        x, y = touch.x, touch.y
        touch.push()
        touch.apply_transform_2d(self.to_local)
        ret = super(AnimationConstructor, self).on_touch_up(touch)
        touch.pop()
        return ret



