__author__ = 'awhite'

from kivy.uix.widget import Widget
from kivy.graphics import Line, Canvas, Color
from kivy.properties import NumericProperty
from kivy.animation import Animation
from kivy.vector import Vector


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


# Extending Scatter didn't work so well, some kind of stacking of Scale/Translate
class ControlPoint(Widget):
    "A visual point used in Mesh animation setup"

    drawn_size = NumericProperty(1.0)
    hole_diam = NumericProperty(1.0)

    def __init__(self, **kwargs):
        self.mesh = None
        self.vertex_index = -1
        self.mesh_attached = False

        # Saved positions
        self.positions = {0:(0,0)}
        self.position_index = 0
        self._animation = None
        self._detach_after_animation = False

        super(ControlPoint, self).__init__(**kwargs)

        print(self.pos)

    def on_touch_down(self, touch):
        if self.disabled:
            return False

        if super(ControlPoint, self).on_touch_down(touch):
            return True

        # convert to center?
        if self.collide_point(*touch.pos):
            touch.grab(self)

            return True

    def on_touch_move(self, touch):
        # Need to return False for Scatter to work when touching this point
        # Not sure why True is returned by Kivy when disabled anyway.
        if self.disabled:
            return False

        if super(ControlPoint, self).on_touch_move(touch):
            return True

        x, y = touch.pos[0], touch.pos[1]
        # If grabbing this point and the move is within bounds of parent, move the point
        if touch.grab_current is self:
            # pos was converted to_local
            # Restrict to parent
            # 0 if < 0, parent.right if > parent.right, otherwise x
            parent = self.parent

            # TODO Fix Hardcoded logic to animation step 0
            if self.position_index == 0:
                # Parents boundary in local coords
                self.center_x = min(max(0, x), parent.width)
                self.center_y = min(max(0, y), parent.height)

            else:
                origin = self.positions[0]
                # Only allow moving if within this distance of first point
                distance_limit = parent.bbox_diagonal
                pos0v = Vector(origin)
                if pos0v.distance((x, y)) < distance_limit:
                    self.center = (x, y)
                else:
                    # Place as far as allowed
                    v = (Vector((x,y)) - Vector(origin)).normalize()
                    self.center = pos0v + v*distance_limit

            return True

        return False


    def on_touch_up(self, touch):
        if self.disabled:
            return False

        if super(ControlPoint, self).on_touch_up(touch):
            return True

        # here, you don't check if the touch collides or things like that.
        # you just need to check if it's a grabbed touch event
        if touch.grab_current is self:

            # ok, the current touch is dispatched for us.
            # do something interesting here

            # don't forget to ungrab ourself, or you might have side effects
            touch.ungrab(self)

            # and accept the last up
            return True

    def on_pos(self, widget, new_pos):
        # Copy values instead of reference to center
        self.positions[self.position_index] = (self.center_x, self.center_y)
        # print('ControlPoint.on_pos', new_pos)
        # if self.parent:
        #     print('ControlPoint vertice coords', self.calc_vertice_coords())

        if self.mesh and self.vertex_index != -1:
            i = self.vertex_index*4
            verts = self.mesh.vertices
            x, y, u, v = self.calc_vertex_coords()
            verts[i], verts[i+1] = x, y
            if not self.mesh_attached:
                # Also update u, v
                verts[i+2], verts[i+3] = u, v

            # Trigger update
            self.mesh.vertices = verts

    def move_to_position_index(self, index, animate=True, detach_mesh_after = False):
        if index < 0:
            raise ValueError('index < 0')

        self.position_index = index

        if index in self.positions:
            if animate:
                # No public method to re-use Animation, so just re-create
                if self._animation is not None:
                    self._animation.cancel(self)

                self._detach_after_animation = detach_mesh_after
                a = Animation(center=self.positions[index], duration=0.7)
                a.bind(on_complete=self._on_animate_complete, on_start=self._on_animate_start)
                a.start(self)
                self._animation = a

            else:
                self.center = self.positions[index]
        else:
            # Position index not set before, save current position at index
            self.positions[index] = (self.center_x, self.center_y)

    def _on_animate_start(self, anim, widget):
        self.disabled = True

    def _on_animate_complete(self, anim, widget):
        self.disabled = False
        if self._detach_after_animation:
            self.attach_mesh(False)
            self._detach_after_animation = False

        self._animation = None

    # def on_disabled(self, instance, value):
    #     print('on_disabled', value)

    def attach_mesh(self, mesh_attached):
        """Attach point movement to mesh so that ControlPoint's pos change changes vertex tex_coords.
        Otherwise, both tex_coords and u, v are changed so no distortion occurs
        """
        self.mesh_attached = mesh_attached

    def get_tex_coords(self, pos_index=None):
        if pos_index is None:
            # Current location
            return self.center_x, self.center_y
        else:
            return self.positions[pos_index]

    def calc_vertex_coords(self, pos_index=None):
        "Get the coordinates used by Mesh.vertices for this point"

        x, y = self.get_tex_coords(pos_index)

        # # Parents boundary in local coords
        # self.center_x = min(max(bbox[0], x), bbox[2])
        # self.center_y = min(max(bbox[1], y), bbox[3])
        #w, h = self.parent.image.norm_image_size
        #w = bbox[4]
        #h = bbox[5]

        #tx = x - bbox[0]
        #ty = y - bbox[1]
        # FIXME Detect need to texture flip
        return (x, y, x/self.parent.width, 1.0 - y/self.parent.height)
