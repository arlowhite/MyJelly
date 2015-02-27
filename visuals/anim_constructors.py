__author__ = 'awhite'

#from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.widget import Widget
from kivy.graphics import Translate, Rectangle
from kivy.uix.image import Image
from kivy.animation import Animation
from kivy.event import EventDispatcher
from kivy.properties import ObjectProperty, ListProperty

from .drawn_visual import ControlPoint

# RelativeLayout or Scatter seems overcomplicated and causes issues
# just do it myself, don't really need to add_widget()
# TODO Padding so can pickup ControlPoint on edge


class JellyAnimation:
    "Animates Mesh vertices"

    # log to upper-right
    # x**# down

class MeshAnimator(EventDispatcher):
    """Animates a Mesh's vertices from one set to another in a loop."""

    def __init__(self, **kwargs):
        super(MeshAnimator, self).__init__(**kwargs)

        self.vertices_states = []


    def add_vertices(self, vertices, duration=1.0, delay=None):
        """Add a set of vertices.
        duration: Seconds taken to reach vertices.
        delay: Seconds to delay before beginning next animation

        duration & delay can be number, function, or generator
        """
        num = len(self.vertices_states)
        if num > 0 and num != len(vertices):
            raise ValueError('Mismatched number of vertices: %d vs %d'%(num, len(vertices)))

        self.vertices_states.append( (vertices, duration, delay) )



class AnimationConstructor(Widget):
    """Visual animation constructor.
    Shows a single Mesh texture in the center.
    Allows manipulation of ControlPoints within its size.

    """

    jelly_data = ObjectProperty(None)
    ctrl_points = ListProperty([])


    def on_jelly_data(self, widget, data):

        # Fit image/Mesh without distortion?
        # need mipmap=True again?
        img = Image(texture=data.bell_image.texture, keep_ratio=True, allow_stretch=True)
        self.image = img

        self.add_widget(img)

    def on_pos(self, widget, pos):
        #self._trans.xy = pos
        self.image.pos = pos

    def on_size(self, widget, size):
        # Fit Image/Mesh within
        self.image.size = size
        # TODO Control points should stay aligned with image


    def calc_verticies(self):
        "Calculate Mesh.vertices from active ControlPoints"
        verts = []

        for cp in self.ctrl_points:
            verts.extend(cp.calc_vertice_coords())

        return verts

    def finalize_control_points(self):
        print('final points')

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

        verts = [x_mean, y_mean, x_mean/self.width, y_mean/self.height]
        verts.extend(self.calc_verticies())

        self.widget.update_mesh_vertices(verts)
        m = self.widget.mesh

        for i, cp in enumerate(self.ctrl_points):
            # First point is the central one above, so add one
            cp.attach_mesh(m, i+1)

    def finalize_point_destinations(self):
        print('dests')
        # TODO Maybe inner-position another animation construction state?
        m = self.widget.mesh
        # Central point
        in_pos = [m.vertices[0], m.vertices[1]]
        out_pos = list(in_pos)

        for cp in self.ctrl_points:
            out_pos.extend(cp.pos)
            in_pos.extend(cp.original_mesh_pos)

        # TODO Decouple Animated Mesh from Jelly
        self.widget.set_bell_animation_vertices(in_pos, out_pos)

    def move_control_points(self, vertices):
        "Move all of the Control Points to the specified x1, y1, x2, y2, ... vertices."

        pass


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



