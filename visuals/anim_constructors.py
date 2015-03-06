__author__ = 'awhite'

import random

from kivy.logger import Logger
from kivy.clock import Clock
from kivy.graphics import Translate, Rectangle, Line, Color, Mesh
from kivy.vector import Vector
from kivy.core.image import Image as CoreImage
from kivy.uix.scatter import ScatterPlane, Scatter
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.stencilview import StencilView
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
            # Currently, u,v come from step 0 and should never be updated again
            self.mesh.vertices = list(self.vertices_states[0][0])

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

    animation_data = ObjectProperty(None)
    control_points = ListProperty([])
    animation_step = BoundedNumericProperty(0, min=0)
    # Image can be moved and zoomed by user to allow more precise ControlPoint placement.
    move_resize = BooleanProperty(False)
    animating = BooleanProperty(False)
    control_points_disabled = BooleanProperty(False)
    control_points_opacity = BoundedNumericProperty(1.0, min=0.0, max=1.0)

    def __init__(self, **kwargs):
        self.mesh_mode = 'triangle_fan'
        self.mesh_attached = False
        self._image_size_set = False
        self.mesh = None
        self._previous_step = 0
        self.faded_image_opacity = 0.5
        super(AnimationConstructor, self).__init__(**kwargs)

        self.bind(move_resize=self.decide_disable_control_points, animating=self.decide_disable_control_points)

        with self.canvas:
            self.image_color = Color(rgba=(1, 1, 1, 1))
            self.image = Rectangle()

            self.mesh_color = Color(rgba=(1, 1, 1, 1))
            self.mesh = Mesh(mode=self.mesh_mode)


    def on_animation_data(self, widget, data):
        """Resets AnimationConstructor, displays image centered"""
        # TODO Work on reseting state? Just create new instead?

        Logger.debug('animation_data set')
        # self has default size at this point, sizing must be done in on_size

        with self.canvas:
            # mipmap=True changes tex_coords and screws up calculations
            # TODO Research mipmap more
            cimage = CoreImage(data.bell_image_filename, mipmap=False)


        texture = cimage.texture

        self.image.texture = texture
        self.mesh.texture = texture
        self.texture = texture
        # TODO Position Image center/zoomed by default
        # Nexus 10 Image is smaller, test density independent
        # TODO Is there any benifit to Image vs Rectangle w/ Texture ?

        # No need for Image if we're not taking advantage of ratio maintaining code
        #img = Image(texture=texture, keep_ratio=True, allow_stretch=True)
        #img.bind(norm_image_size=self.on_norm_image_size)
        #self.add_widget(img)

        # Just set Scatter and Rectangle to texture size
        self.image.size = texture.size
        self.size = texture.size
        # Will be positioned and scalled in on_parent_size

        self.animation_step = 0


    def on_parent(self, _, parent):
        parent.bind(size=self.on_parent_size)

    def on_parent_size(self, widget, size):
        print(self.__class__.__name__ + '.on_parent_size', size)
        p_width, p_height = size

        # Ignore default/zero sizes
        if p_height == 0.0 or p_height == 1:
            print('ignoring size', size)
            return

        # self size is always set to Image size, instead just re-center and re-scale
        # Idea: Maybe avoid this if user has moved-resized?

        # Fit Image/Mesh within
        #self.image.size = size
        # TODO Control points should stay aligned with image
        #print(self.__class__.__name__, 'on_size', size)
        # FIXME Updating Image.size messes up ControlPoint references
        # Only do this once
        # if self._image_size_set:
        #     return
        # self.image.size = size
        # self._image_size_set = True
        img = self.image
        self.center = self.parent.center

        # scale up to fit, whichever dimension is smaller
        h_scale = p_height/float(self.height)
        w_scale = p_width/float(self.width)
        self.scale = min(h_scale, w_scale)


    def on_size(self, _, size):
        print(self.__class__.__name__ + '.on_size', size)
        self.bbox_diagonal = (size[0]**2 + size[1]**2)**0.5

    def on_control_points(self, widget, points):
        # If on first animation step, Update mesh to preview Mesh cut
        if self.animation_step == 0 and len(points) >= 3:
            self.calc_mesh_verticies(step = 0)

            # Fade image a bit
            #if self.image.opacity > self.faded_image_opacity:
                #Animation(opacity=self.faded_image_opacity).start(self.image)

            Animation(a=self.faded_image_opacity).start(self.image_color)


    def on_animation_step(self, widget, step):
        """What step to activate.
        0: Position points on image
        1: Outer Bell
        2: Closed Bell (Optional)
        """
        print('on_animation_step', step)

        resume_animation = self.animating
        if self.animating:
            # Switched step while previewing animation
            self.preview_animation(False)

        if step == 0:
            Animation(a=self.faded_image_opacity).start(self.image_color)
            # Mesh will be detached after animation
            self.mesh_attached = False

        else:
            # Not first animation step
            Animation(a=0.0).start(self.image_color)

            mesh = self.mesh

            if self._previous_step == 0:
                # Redo base vertices when moving from 0 to other
                Logger.debug('Recalculating vertices/indices during transition from step 0')
                self.calc_mesh_verticies(step = 0)

            if not self.mesh_attached:
                # attach before moving to other animation steps
                for cp in self.control_points:
                    cp.attach_mesh(True)

                self.mesh_attached = True


        self.move_control_points(step, detach_mesh_after=step==0)

        self._previous_step = step

        if resume_animation:
            self.preview_animation()

    def calc_mesh_verticies(self, step = None, update_mesh = True):
        """Calculate Mesh.vertices and indices from the ControlPoints
        If step omitted, vertices at current position, otherwise
        vertices at that animation step.
        Central vertice at center is added as first item in list

        returns vertices, indices
        """

        num = len(self.control_points)
        triangle_fan_mode = self.mesh_mode == 'triangle_fan'

        verts = []
        cent_x, cent_y, cent_u, cent_v = 0.0, 0.0, 0.0, 0.0

        # Need to calculate Centroid first, then do pass through to calculate vertices
        for cp in self.control_points:
            tx, ty = cp.get_tex_coords(step)
            cent_x += tx
            cent_y += ty

        cent_x /= num
        cent_y /= num


        if triangle_fan_mode and step==0:
            # Sort by angle from centroid in case user didn't place around perimeter in order

            cent_vec = Vector(cent_x, cent_y)
            ref = Vector(1, 0) # Reference vector to measure angle from
            for cp in self.control_points:
                cp.centroid_angle = ref.angle(Vector(cp.get_tex_coords(step)) - cent_vec)

            # ListProperty.sort does not exist
            #self.control_points.sort(key = lambda cp: cp.centroid_angle)
            self.control_points = sorted(self.control_points, key = lambda cp: cp.centroid_angle)

        # TODO Need to figure out similar solution if using triangle_strip

        # Create vertices list
        # centroid added as first vertex in triangle-fan mode
        start = 1 if triangle_fan_mode else 0
        for index, cp in enumerate(self.control_points, start = start):
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
        for cp in self.control_points:
            cp.move_to_position_index(position_index, detach_mesh_after=detach_mesh_after)


    def preview_animation(self, activate_preview=True):
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
            self.animating = True
            a.start_animation()

        elif self.mesh_animator:
            self.mesh_animator.stop_animation()

            # Set Mesh.vertices back to current step's by pretending pos just set
            for cp in self.control_points:
                cp.on_pos(cp, cp.pos)

            self.animating = False


    def collide_point(self, x, y):
        # Make it behave like ScatterPlane, but restricted to parent
        return self.parent.collide_point(x, y)

    def on_move_resize(self, widget, enabled):
        self.do_translation = enabled
        self.do_scale = enabled

    def decide_disable_control_points(self, _, __):
        # Called when move_resize or animating changes
        self.control_points_disabled = self.move_resize or self.animating
        self.control_points_opacity = 0.0 if self.animating else 0.5 if self.move_resize else 1.0

    def on_control_points_disabled(self, _, disable):
        Logger.debug("AnimationConstructor: disable_control_points. disable=%s", disable)
        for cp in self.control_points:
            cp.disabled = disable

    def on_control_points_opacity(self, _, opacity):
        a = Animation(duration=0.5, opacity=opacity)
        for cp in self.control_points:
            a.start(cp)

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

        if self.move_resize:
            # Defer to Scatter
            return super(AnimationConstructor, self).on_touch_down(touch)


        # Otherwise, find nearest ControlPoint
        # We must take over children's on_touch_down since having them check who's closest instead of the parent
        assert len(self.children) == len(self.control_points)

        touch.push()
        try:
            touch.apply_transform_2d(self.to_local)
            transformed_x, transformed_y = touch.x, touch.y

            if self.children:
                touch_vec = Vector(transformed_x, transformed_y)

                closest = None
                closest_dist = 0
                for child in self.children:
                    if child.disabled:
                        continue

                    # Distance from touch to child
                    dist = touch_vec.distance(child.pos)
                    if closest is None or dist < closest_dist:
                        closest = child
                        closest_dist = dist

                if closest is None:
                    # All children disabled
                    return False

                # Grab closest if within certain distance
                elif closest_dist < closest.width/1.5:
                    closest.pos = transformed_x, transformed_y
                    touch.grab(closest)
                    return True

            # No children or none close enough

            if self.animation_step != 0:
                # Only create ControlPoints in first step
                return False

            # None were close enough, create a new ControlPoint
            ctrl_pt = ControlPoint()
            ctrl_pt.mesh = self.mesh

            self.add_widget(ctrl_pt)

            # Use transformed coordinates
            ctrl_pt.pos = (transformed_x, transformed_y)

            # cp.vertex_index will be set within on_ctrl_points
            self.control_points.append(ctrl_pt)
            # Grab right away so user can create and move in one touch
            touch.grab(ctrl_pt)

            return True

        finally:
            # Always pop when returning from try block where we did touch.push()
            touch.pop()



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



