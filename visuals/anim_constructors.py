__author__ = 'awhite'

from kivy.graphics import Translate, Rectangle, Line, Color
from kivy.uix.image import Image
from kivy.uix.scatter import ScatterPlane, Scatter
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.stencilview import StencilView
from kivy.uix.carousel import Carousel
from kivy.animation import Animation
from kivy.event import EventDispatcher
from kivy.properties import ObjectProperty, ListProperty, BoundedNumericProperty

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


class FloatLayoutStencilView(FloatLayout, StencilView):
    pass

# Issues:
# Idea: Currently, ControlPoints scale with Scatter, could reverse/reduce this with an opposite Scale maybe.
# ScatterPlane works by changing collide_point,

class AnimationConstructor(Scatter):
    """Visual animation constructor.
    Shows a single Mesh texture in the center.
    Allows manipulation of ControlPoints within its size.

    """

    jelly_data = ObjectProperty(None)
    ctrl_points = ListProperty([])
    animation_step = BoundedNumericProperty(0, min=0)
    # Image can be moved and zoomed by user to allow more precise ControlPoint placement.
    #image_unlocked = BooleanProperty(False)

    def __init__(self, **kwargs):
        self._image_size_set = False
        self.control_point_bbox = [0, 0, 1, 1]
        super(AnimationConstructor, self).__init__(**kwargs)


    def on_jelly_data(self, widget, data):
        # self has default size at this point, sizing must be done in on_size
        # Image will be fit within size once in self.on_size
        # need mipmap=True again?
        img = Image(texture=data.bell_image.texture, keep_ratio=True, allow_stretch=True)

        self.image = img
        img.bind(norm_image_size=self.on_norm_image_size)

        self.add_widget(img)


    # TODO Get rid of? just visualizing image
    def on_norm_image_size(self, widget, size):
        # Calculating the Image bounding box coordinates to limit ControlPoints to
        # pos/center is in window coordinates, just use size
        half_w = self.width / 2.0
        half_h = self.height / 2.0
        half_iw = size[0] / 2.0
        half_ih = size[1] / 2.0

        bbox = self.control_point_bbox
        # Bottom-Left bound
        bbox[0] = half_w - half_iw
        bbox[1] = half_h - half_ih
        # Upper-right bound
        bbox[2] = half_w + half_iw
        bbox[3] = half_h + half_ih

        print('on_norm_image_size', size, 'control_point_bbox', bbox)


    # Size does not change when scaling Scatter, only when window changes
    def on_size(self, widget, size):
        if size[1] == 0.0:
            print('ignoring zero height', size)
            return

        # Fit Image/Mesh within
        #self.image.size = size
        # TODO Control points should stay aligned with image
        print(self.__class__.__name__, 'on_size', size)
        # FIXME Updating Image.size messes up ControlPoint references
        # Only do this once
        if self._image_size_set:
            return
        self.image.size = size
        self._image_size_set = True


    def on_animation_step(self, widget, step):
        """What step to activate.
        0: Position points on image
        1: Outer Bell
        2: Closed Bell (Optional)
        """
        print('on_animation_step', step)

        for cp in self.ctrl_points:
            cp.move_to_position_index(step)

        if step==1:
            # Expand control_point_bbox
            pass



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


    def collide_point(self, x, y):
        # Make it behave like ScatterPlane, but restricted to parent
        return self.parent.collide_point(x, y)

    def on_touch_down(self, touch):

        # if self.image_unlocked:
            # Defer to Scatter implementation
            # return super(AnimationConstructor, self).on_touch_down(touch)

        # Otherwise manipulate ControlPoints instead of Scatter doing anything
        # handled = super(AnimationConstructor, self).on_touch_down(touch)
        # if handled:
        #     return True


        x, y = touch.x, touch.y
        # Other Widgets, e.g. Button need us to return False to work
        if not self.collide_point(x, y):
            return False


        handled = super(AnimationConstructor, self).on_touch_down(touch)

        if not handled:
            touch.push()
            touch.apply_transform_2d(self.to_local)

            # Create a new ControlPoint
            ctrl_pt = ControlPoint()

            # Use transformed coordinates
            ctrl_pt.center = (touch.x, touch.y)

            # TODO Decide whether to add to scatter or not, maybe make this inherit Scatter?
            self.add_widget(ctrl_pt)
            # TODO Create ControlPoint container of some kind
            self.ctrl_points.append(ctrl_pt)

            touch.pop()
            return True

        return handled

        # Using Scatter now, need to think about, not needed I think
    # def on_touch_move(self, touch):
    #     x, y = touch.x, touch.y
    #     touch.push()
    #     touch.apply_transform_2d(self.to_local)
    #     ret = super(AnimationConstructor, self).on_touch_move(touch)
    #     touch.pop()
    #     return ret
    #
    # def on_touch_up(self, touch):
    #     x, y = touch.x, touch.y
    #     touch.push()
    #     touch.apply_transform_2d(self.to_local)
    #     ret = super(AnimationConstructor, self).on_touch_up(touch)
    #     touch.pop()
    #     return ret



