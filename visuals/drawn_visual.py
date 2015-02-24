__author__ = 'awhite'

from kivy.uix.widget import Widget
#from kivy.uix.scatter import Scatter
from kivy.uix.relativelayout import RelativeLayout
from kivy.graphics import Line, Canvas, Color


class Path:
    "Visual indication of a path to follow"

    def __init__(self, canvas, x, y):

        c = Canvas()
        self.canvas = c

        with c:
            Color(1, 0, 0, 0.4)
            self.line = Line(points=(x, y), width=2)

        canvas.add(c)

    def add_point(self, x, y):
        self.line.points += (x, y)


    def __getitem__(self, item):
        # http://stackoverflow.com/questions/2936863/python-implementing-slicing-in-getitem
        if isinstance( item, slice ) :
            #Get the start, stop, and step from the slice
            return [self[ii] for ii in xrange(*item.indices(len(self)))]
        elif isinstance( item, int ) :
            if item < 0 : #Handle negative indices
                item += len( self )
            if item >= len( self ) :
                raise IndexError, "The index (%d) is out of range."%item

            return (self.line.points[2*item], self.line.points[2*item+1])
        else:
            raise TypeError, "Invalid argument type."

    def __len__(self):
        return len(self.line.points)/2

    def pop(self, num):
        if num != 0:
            raise ValueError('Code only designed to pop first element!')

        x = self.line.points.pop(0)
        y = self.line.points.pop(0)
        return (x,y)

    def smooth(self):
        # TODO Smooth path
        pass


class ControlPoint(Widget):
    "A visual point used in Mesh animation setup"

    def on_touch_down(self, touch):
        print('mypos', self.pos, 'touchpos', touch.pos)
        # convert to center?
        if self.collide_point(*touch.pos):
            touch.grab(self)

            return True

    def on_touch_move(self, touch):
        pos = touch.pos
        # If grabbing this point and the move is within bounds of parent, move the point
        if touch.grab_current is self:
            # pos was converted to_local
            # Restrict to parent
            # 0 if < 0, parent.right if > parent.right, otherwise x

            # Parents boundary in local coords
            p_right, p_top = self.parent.to_local(self.parent.right, self.parent.top)
            self.center_x = min(max(0, pos[0]), p_right)
            self.center_y = min(max(0, pos[1]), p_top)

            return True

        return False


    def on_touch_up(self, touch):
        # here, you don't check if the touch collides or things like that.
        # you just need to check if it's a grabbed touch event
        if touch.grab_current is self:

            # ok, the current touch is dispatched for us.
            # do something interesting here

            # don't forget to ungrab ourself, or you might have side effects
            touch.ungrab(self)

            # and accept the last up
            return True

    def get_vertice_coords(self):
        "Get the coordinates used by Mesh.vertices for this point"
        a = self.to_local(self.center_x, self.center_y)
        b = self.to_widget(self.center_x, self.center_y)
        print(a)
        print(b)

