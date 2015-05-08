from kivy.uix.widget import Widget
from kivy.graphics import Line, Canvas, Color
from kivy.properties import NumericProperty, BooleanProperty
from kivy.animation import Animation
from kivy.vector import Vector
from kivy.metrics import dp

from animations import setup_step

__author__ = 'awhite'

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

    natural_size = NumericProperty(1.0)  # size will be scaled, so this is the default/natural size
    drawn_size = NumericProperty(1.0)
    hole_diam = NumericProperty(1.0)

    hide_trail_line = BooleanProperty(False)

    def __init__(self, **kwargs):
        self.mesh = None
        self.vertex_index = -1
        self.mesh_attached = False
        self.moved_point_trigger = kwargs['moved_point_trigger']

        # Saved positions
        self.positions = {}
        self.position_index = None
        self._animation = None  # The Animation instance if animating
        self._detach_after_animation = False

        super(ControlPoint, self).__init__(**kwargs)

        # Line always white!?
        # Tried on_canvas, didn't make a difference.
        # with self.canvas:
        # self.trail_line_color = Color(rgba=(0.1, 1.0, 1.0, 1.0))
        # self.trail_line = Line(width=dp(1.0))

        # For some reason, color is only working when set in KV.
        for instruction in self.canvas.before.children:
            if isinstance(instruction, Line):
                self.trail_line = instruction

    def on_touch_down(self, touch):
        # Return False instead of True so Scatter works with dragging ControlPoint
        # For other touch_down events, parent handles logic
        if self.disabled:
            return False

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
            if self.position_index == setup_step:
                # Parents boundary in local coords
                self.x = min(max(0, x), parent.width)
                self.y = min(max(0, y), parent.height)

            else:
                origin = self.positions[setup_step]
                # Only allow moving if within this distance of first point
                distance_limit = parent.bbox_diagonal
                pos0v = Vector(origin)
                if pos0v.distance((x, y)) < distance_limit:
                    self.pos = (x, y)
                else:
                    # Place as far as allowed
                    v = (Vector((x,y)) - Vector(origin)).normalize()
                    self.pos = pos0v + v*distance_limit

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
        # Update position if not within animation
        if not self._animation:
            # Copy values instead of reference to pos
            self.positions[self.position_index] = (self.x, self.y)
            self.update_trail_line()

        self.moved_point_trigger()

        # Want to preview centroid update so need to re-run calc anyway
        # parent now sets-up a trigger
        # TODO refactor: may as well forget whole attached_mesh thing?
        # if self.mesh and self.vertex_index != -1:
            # i = self.vertex_index*4
            # verts = self.mesh.vertices
            # x, y, u, v = self.calc_vertex_coords()
            # try:
            #     verts[i], verts[i+1] = x, y
            #     if not self.mesh_attached:
            #         # Also update u, v
            #         verts[i+2], verts[i+3] = u, v
            #
            #     # Trigger update
            #     self.mesh.vertices = verts
            #
            # except IndexError:
            #     pass

    def on_parent(self, _, parent):
        if hasattr(parent, 'scale'):
            parent.bind(scale=self.on_parent_scale)
            self.on_parent_scale(parent, parent.scale)

    def on_parent_scale(self, _, scale):
        self.size = self.natural_size / scale, self.natural_size / scale


    def move_to_position_index(self, index, animate=True, detach_mesh_after = False):
        self.position_index = index

        pos = self.get_tex_coords(index)

        if animate:
            # No public method to re-use Animation, so just re-create
            if self._animation is not None:
                self._animation.cancel(self)

            self._detach_after_animation = detach_mesh_after
            a = Animation(pos=pos, duration=0.4)
            a.bind(on_complete=self._on_animate_complete, on_start=self._on_animate_start)
            a.start(self)

        else:
            self.pos = pos
            if detach_mesh_after:
                self.attach_mesh(False)

    def on_hide_trail_line(self, _, hide):
        if hide:
            self.canvas.before.clear()

        else:
            self.canvas.before.add(self.trail_line)


    def update_trail_line(self):
        "Update line that shows how point moves through animation"

        if not hasattr(self, 'trail_line'):
            return

        parent = self.parent

        points = []
        for step in parent.step_order:
            parent.get_horiz_transition(step)
            parent.get_vert_transition(step)


            points.extend(self.positions[step])

        self.trail_line.points = points

    def _on_animate_start(self, anim, widget):
        self.disabled = True
        self._animation = anim

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
            return self.x, self.y
        else:
            # May not exist if ControlPoint.pos was never set while on this position
            # However, needs a valid value for animation data serialization callers
            # Default to setup position
            if pos_index not in self.positions:
                setup_pos = self.positions[setup_step]
                self.positions[pos_index] = (setup_pos[0], setup_pos[1])

            return self.positions[pos_index]

    def calc_vertex_coords(self, pos_index=None):
        "Get the coordinates used by Mesh.vertices for this point"

        x, y = self.get_tex_coords(pos_index)

        # Parents box defines tex_coords

        # FIXME Detect need to texture flip
        return (x, y, x/self.parent.width, 1.0 - y/self.parent.height)
