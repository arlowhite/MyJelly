__author__ = 'awhite'

import random

from kivy.logger import Logger
from kivy.clock import Clock
from kivy.graphics import Translate, Rectangle, Line, Color, Mesh
from kivy.vector import Vector
from kivy.core.image import Image as CoreImage
from kivy.uix.image import Image
from kivy.uix.scatter import ScatterPlane, Scatter
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.stencilview import StencilView
from kivy.uix.carousel import Carousel
from kivy.animation import Animation
from kivy.event import EventDispatcher
from kivy.properties import ObjectProperty, ListProperty, BoundedNumericProperty, BooleanProperty, NumericProperty

from .drawn_visual import ControlPoint
from misc.util import evaluate_thing

# RelativeLayout or Scatter seems overcomplicated and causes issues
# just do it myself, don't really need to add_widget()
# TODO Padding so can pickup ControlPoint on edge


class JellyAnimation:
    "Animates Mesh vertices"

    # log to upper-right
    # x**# down

# TODO Need to serialize this into JellyData somehow
class MeshAnimator(EventDispatcher):
    """Animates a Mesh's vertices from one set to another in a loop.
    Programmer should set MeshAnimator.mesh and make sure indices on Mesh are set.
    """

    # variables that are animated and used to adjust vertices
    horizontal_fraction = NumericProperty(0.0)
    vertical_fraction = NumericProperty(0.0)

    # The current step is the animation step animating to, step remains during optionaly delay
    # As soon as next step starts animating, step is incremented
    step = NumericProperty(0)

    def __init__(self, **kwargs):
        self.vertices_states = []
        self.previous_step = 0
        self._animation = None
        self._setup = False
        super(MeshAnimator, self).__init__(**kwargs)


    def add_vertices(self, vertices, duration=1.0, delay=None,
                     horizontal_transition='linear', vertical_transition='linear'):
        """Add a set of vertices.
        duration: Seconds taken to reach vertices at this step.
        delay: Seconds to delay before beginning next animation after this step.
        horizontal|vertical_transition: transition to use when transferring to vertices at this step.

        duration & delay can be number, function, or generator
        """
        num = len(self.vertices_states)
        if num > 0 and len(self.vertices_states[0][0]) != len(vertices):
            raise ValueError('Mismatched number of vertices: %d vs %d'%(num, len(vertices)))

        self.vertices_states.append( (vertices, duration, delay, horizontal_transition, vertical_transition) )


    # TODO Maybe remove if not used much
    def next_step(self):
        "Get the next step, looping to 0 if at end"
        step = self.step + 1
        if step >= len(self.vertices_states):
            step = 0

        return step


    def start_animation(self, step=None):
        """Start animating to the specified step from the one previous.
        If not specified, goes to next step (modifying step/previous_step)"""

        # Idea: If needed, could add temporary animation that morphs from current Mesh.vertices

        num_states = len(self.vertices_states)
        if num_states < 2:
            # raise instead?
            return

        if step is None:
            step = self.next_step()

        prev = step - 1
        if prev < 0:
            prev = num_states - 1

        self.previous_step = prev
        self.step = step

        if not self._setup:
            # Set initial vertices
            # Currently, u,v never updated again
            self.mesh.vertices = list(self.vertices_states[self.previous_step][0])

            self._setup = True

        step = self.vertices_states[self.step]
        dur = evaluate_thing(step[1])

        # Setting properties will set vertices to previous_step
        self.horizontal_fraction = 0.0
        self.vertical_fraction = 0.0

        # Go from 0 to 1 each time, try saving Animation
        # PERF try keeping Animation instance, need to change transition/duration each time
        a = Animation(horizontal_fraction=1.0, transition=step[3], duration=dur)
        a &= Animation(vertical_fraction=1.0, transition=step[4], duration=dur)
        a.bind(on_complete=self.on_animation_complete)
        self._animation = a
        a.start(self)

    def stop_animation(self):
        if not self._animation:
            return

        # Don't want to call on_complete
        self._animation.cancel(self)
        self._animation = None


    def on_animation_complete(self, anim, widget):
        # Delay after current step
        delay_thing = self.vertices_states[self.step][2]
        if delay_thing:
            Clock.schedule_once(self.start_animation, evaluate_thing(delay_thing))

        else:
            self.start_animation()


    # def on_horizontal_fraction(self, *args):
    #     print('on_horizontal_fraction', args)

    def on_vertical_fraction(self, widget, vert):
        # print('on_vertical_fraction', vert)

        # Do all work in one event function for efficency (horizontal should have been updated before this because of creation order.
        # TODO: Measure performance. Numpy math? Kivy Matrix math?

        horiz = self.horizontal_fraction

        in_verts = self.vertices_states[self.previous_step][0]
        out_verts = self.vertices_states[self.step][0]

        mesh = self.mesh
        verts = mesh.vertices
        # Skip central point, Go through by 4's
        # Vertex lists conform to Mesh.vertices
        for x in range(0, len(in_verts), 4):
            x_coord = (out_verts[x]-in_verts[x]) * horiz + in_verts[x]
            y = x+1
            y_coord = (out_verts[y]-in_verts[y]) * vert + in_verts[y]

            verts[x] = x_coord
            verts[y] = y_coord

        mesh.vertices = verts




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
    move_resize = BooleanProperty(False)

    def __init__(self, **kwargs):
        self.mesh_mode = 'triangle_fan'
        self.mesh_attached = False
        self._image_size_set = False
        self.control_point_bbox = [0, 0, 1, 1, 1, 1]
        self.mesh = None
        self._previous_step = 0
        self.faded_image_opacity = 0.5
        super(AnimationConstructor, self).__init__(**kwargs)

        with self.canvas:
            self.mesh_color = Color(rgba=(1, 1, 1, 1))
            self.mesh = Mesh(mode=self.mesh_mode)


    def on_jelly_data(self, widget, data):
        # self has default size at this point, sizing must be done in on_size
        # Image will be fit within size once in self.on_size
        # need mipmap=True again?
        #texture = data.bell_image.texture
        with self.canvas:
            # mipmap=True changes tex_coords and screws up calculations
            # TODO Research mipmap more
            cimage = CoreImage(data.bell_image_filename, mipmap=False)
            texture = cimage.texture


        self.mesh.texture = texture
        self.texture = texture
        # TODO Position Image center/zoomed by default
        # Nexus 10 Image is smaller, test density independent
        # TODO Is there any benifit to Image vs Rectangle w/ Texture ?
        img = Image(texture=texture, keep_ratio=True, allow_stretch=True)
        img.bind(norm_image_size=self.on_norm_image_size)
        img.size = texture.size
        self.image = img
        self.add_widget(img)

        # Rectangle with texture looks the same
        # with self.canvas:
        #     Rectangle(texture=texture, pos=(0,0), size=texture.size)


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

        # Store image width & height for efficency
        bbox[4] = size[0]
        bbox[5] = size[1]

        # This simple?
        bbox[0] = 0
        bbox[1] = 0
        bbox[2] = size[0]
        bbox[3] = size[1]

        # Used for ControlPoint animation limits
        self.bbox_diagonal = (size[0]**2 + size[1]**2)**0.5

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
        # if self._image_size_set:
        #     return
        # self.image.size = size
        # self._image_size_set = True

    def on_ctrl_points(self, widget, points):
        # If on first animation step, Update mesh to preview Mesh cut
        if self.animation_step == 0 and len(points) >= 3:
            self.calc_mesh_verticies(step = 0)

            # Fade image a bit
            if self.image.opacity > self.faded_image_opacity:
                Animation(opacity=self.faded_image_opacity).start(self.image)


    def on_animation_step(self, widget, step):
        """What step to activate.
        0: Position points on image
        1: Outer Bell
        2: Closed Bell (Optional)
        """
        print('on_animation_step', step)

        if step == 0:
            Animation(opacity=self.faded_image_opacity).start(self.image)
            # Mesh will be detached after animation
            self.mesh_attached = False

        else:
            # Not first animation step
            Animation(opacity=0.0).start(self.image)

            if not self.mesh:
                self.create_mesh()

            mesh = self.mesh

            if self._previous_step == 0:
                # Redo base vertices when moving from 0 to other
                Logger.debug('Recalculating vertices/indices during transition from step 0')
                self.calc_mesh_verticies(step = 0)

            if not self.mesh_attached:
                # attach before moving to other animation steps
                for cp in self.ctrl_points:
                    cp.attach_mesh(True)

                self.mesh_attached = True


        self.move_control_points(step, detach_mesh_after=step==0)

        self._previous_step = step

    def calc_mesh_verticies(self, step = None, update_mesh = True):
        """Calculate Mesh.vertices and indices from the ControlPoints
        If step omitted, vertices at current position, otherwise
        vertices at that animation step. For step 0, u, v coordinates and indices are calculated.
        Central vertice at center is added as first item in list

        returns vertices, indices
        """

        num = len(self.ctrl_points)
        triangle_fan_mode = self.mesh_mode == 'triangle_fan'

        verts = []
        cent_x, cent_y, cent_u, cent_v = 0.0, 0.0, 0.0, 0.0

        # Need to calculate Centroid first, then do pass through to calculate vertices
        for cp in self.ctrl_points:
            tx, ty = cp.get_tex_coords(step)
            cent_x += tx
            cent_y += ty

        cent_x /= num
        cent_y /= num


        if triangle_fan_mode and step==0:
            # Sort by angle from centroid in case user didn't place around perimeter in order

            cent_vec = Vector(cent_x, cent_y)
            ref = Vector(1, 0) # Reference vector to measure angle from
            for cp in self.ctrl_points:
                cp.centroid_angle = ref.angle(Vector(cp.get_tex_coords(step)) - cent_vec)

            # ListProperty.sort does not exist
            #self.ctrl_points.sort(key = lambda cp: cp.centroid_angle)
            self.ctrl_points = sorted(self.ctrl_points, key = lambda cp: cp.centroid_angle)

        # TODO Need to figure out similar solution if using triangle_strip

        # Create vertices list
        # centroid added as first vertex in triangle-fan mode
        start = 1 if triangle_fan_mode else 0
        for index, cp in enumerate(self.ctrl_points, start = start):
            coords = cp.calc_vertex_coords(pos_index=step)
            # Need to calculate u, v centroid still
            cent_u += coords[2]
            cent_v += coords[3]

            cp.vertex_index = index
            verts.extend(coords)

        cent_u /= num
        cent_v /= num

        if triangle_fan_mode:
            # Calculate mean centroid and add to beginning of vertices
            verts.insert(0, cent_v)
            verts.insert(0, cent_u)
            verts.insert(0, cent_y)
            verts.insert(0, cent_x)

            # PERF: Technically don't need to recalculate indices except step 0, but not bothering with optimization now
            indices = range(1, num + 1)
            indices.insert(0, 0)
            indices.append(1)

        else:
            indices = range(num)

        if update_mesh:
            self.mesh.vertices = verts
            self.mesh.indices = indices

        return verts, indices

    def move_control_points(self, position_index, detach_mesh_after):
        "Move all of the Control Points to the specified position index"
        for cp in self.ctrl_points:
            cp.move_to_position_index(position_index, detach_mesh_after=detach_mesh_after)


    def preview_animation(self, activate_preview):
        "Start/Stop animation preview"

        if activate_preview:
            a = MeshAnimator()
            a.mesh = self.mesh

            bell_horiz_transition_out = 'in_back'
            bell_vert_transition_out = 'out_cubic'
            bell_horiz_transition_in = 'in_sine'
            bell_vert_transition_in = 'out_back'
            # TODO delay random.triangular(0.3, 2.0, 0.5)

            # Iterate steps from 0 to the current one
            for step in range(self.animation_step+1):
                verts, _ = self.calc_mesh_verticies(step=step, update_mesh=False)
                a.add_vertices(verts, duration=0.5, horizontal_transition='in_back', vertical_transition='out_cubic')

            self.mesh_animator = a
            a.start_animation()

        elif self.mesh_animator:
            self.mesh_animator.stop_animation()

            # Set Mesh.vertices back to current step's
            self.calc_mesh_verticies(step=self.animation_step)



    def collide_point(self, x, y):
        # Make it behave like ScatterPlane, but restricted to parent
        return self.parent.collide_point(x, y)

    def on_move_resize(self, widget, enabled):
        self.do_translation = enabled
        self.do_scale = enabled
        for cp in self.ctrl_points:
            cp.disabled = enabled


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
            if self.animation_step != 0:
                return handled

            touch.push()
            touch.apply_transform_2d(self.to_local)

            # Create a new ControlPoint
            ctrl_pt = ControlPoint()

            # Use transformed coordinates
            ctrl_pt.center = (touch.x, touch.y)
            ctrl_pt.mesh = self.mesh


            self.add_widget(ctrl_pt)
            # cp.vertex_index will be set within on_ctrl_points
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



