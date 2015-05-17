__author__ = 'awhite'

import random
from math import cos, sin, radians, degrees, pi

from kivy.logger import Logger
from kivy.graphics import Rectangle, Triangle, Color, Rotate, Translate, InstructionGroup, PushMatrix, PopMatrix, \
    PushState, PopState, Canvas, Mesh, Scale, Ellipse, Line
from kivy.vector import Vector
from kivy.core.image import Image as CoreImage
from kivy.core.image import ImageLoader
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, BoundedNumericProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import StencilUse
from kivy.graphics.instructions import InstructionGroup
from kivy.clock import Clock

import cymunk as phy
from cymunk import Vec2d

from drawn_visual import ControlPoint
from animations import MeshAnimator, setup_step


def fix_angle(angle):
    # Convert angle in degrees to the equivalent angle from -180 to 180
    if angle > 0:
        angle %= 360
    else:
        angle %= -360

    # angle will now be between -360 and 360, now clip to 180
    if angle > 180:
        return -360 + angle

    elif angle < -180:
        return 360 + angle

    return angle

# Don't think I want event dispatch, not needed for every creature and will be too much

# In Sacrifical Creatures I didn't want the overhead of Widgets, but in this game
# I'll try them out since it should make things easier and provide some practice

# TODO Probably just do EventDispatcher instead of Widget? Performance test # of Jellies limit
# Single animation update loop instead of Animation Clocks for each? or chain Animations? &=
class Creature(Widget):
    """Visual entity that moves around (update called on game tick)
     and is attached to the Cymunk physics system"""

    scale = NumericProperty(1.0)

    # 0 points right, positive is counter-clockwise
    # angle in degrees. Converted to -180 to 180
    angle = BoundedNumericProperty(0.0, min=-180.0, max=180.0, errorhandler=fix_angle)

    speed = NumericProperty(0.0)

    def __init__(self, **kwargs):

        self.debug_visuals = True
        # units?? Make KivyProperty? defaults?
        self.orienting = False  # is currently orienting toward orienting_angle
        self.orienting_angle = 0
        self.orienting_throttle = 1.0

        # TODO think about scaling mass volume cubic?
        mass = 1e5  # mass of the body i.e. linear moving inertia
        moment = 1e5  # moment of inertia, i.e. rotation inertia
        mass = 100
        self.phy_body = body = phy.Body(mass, moment)
        self.phy_body.velocity_limit = 1000

        self.body_parts = []

        #box = phy.Poly.create_box(body, size=(200, 100))
        radius = 100
        self.phy_shape = phy.Circle(body, radius, (0, 0))
        self.phy_shape.friction = 0.4
        self.phy_shape.elasticity = 0.3
        #body.position = 400, 100  # set some position of body in simulated space coordinates

        super(Creature, self).__init__(**kwargs)
        body.position = self.pos

        self.draw()

        # .draw() needs to create ._trans before on_pos, so late bind
        self.bind(pos=self.on_pos_changed)

    def bind_physics_space(self, space):
        '''Attach to the given physics space'''
        space.add(self.phy_body, self.phy_shape)  # add physical objects to simulated space
        #self.phy_body.activate()

        for bp in self.body_parts:
            bp.bind_physics_space(space)

    def draw(self):
        with self.canvas.before:
            PushMatrix()
            PushState()

        with self.canvas.after:
            PopMatrix()
            PopState()


        with self.canvas:
            self._color = Color(1, 1, 1, 1)

            # Control size without recalculating vertices
            self._scale = Scale(1, 1, 1)

            # Translate graphics to Creature's position
            self._trans = Translate()
            self._trans.xy = self.pos

            if self.debug_visuals:
                # Need to undo rotation when drawing orienting line
                PushMatrix()

            self._rot = Rotate()
            self._rot.angle = self.angle - 90

            self.draw_creature()

            if self.debug_visuals:
                # Triangle at pos oriented toward angle (within Rotate transform)
                Color(rgba=(1, 0, 0, 0.6))
                x = 6
                Triangle(points=(-x, -x, x, -x, 0, x))

                PopMatrix()

                # Orienting Line
                Color(rgba=(0.0, 1.0, 0.0, 0.8))
                self._orienting_line = Line(width=1.2)



    def move(self, x, y):
        """Set position in physics and visual systems"""
        old_pos = Vec2d(self.phy_body.position)
        self.phy_body.position = x, y
        self.pos = x, y

        # Move body parts as well
        # TODO actually move body part visual as well instead of relying on update() to do it
        for bp in self.body_parts:
            bp.phy_body.position = self.phy_body.position + (bp.phy_body.position - old_pos)

    def change_angle(self, angle):
        """Set angle (degrees) in physics and visual systems"""
        self.phy_body.angle = radians(angle)
        self.angle = angle


    def on_pos_changed(self, jelly_obj, coords):
        self._trans.xy = coords

    def on_scale(self, _, scale):
        # TODO what does z do for 2D?
        self._scale.xyz = (scale, scale, 1.0)

    def on_angle(self, _, angle):
        self._rot.angle = angle - 90  # rotate 90 deg clockwise to correct direction
        # FIXME angle%360? or -180 to 180  see what Scale does
        # TODO update physics

        #self.canvas.ask_update()  # TODO update necessary?


    def orient(self, angle, throttle=1.0):
        """Orient the Creature toward the angle, using body motion
        throttle 0.0 to 1.0 for how quickly to rotate
        """
        self.orienting = True
        self.orienting_angle = angle = fix_angle(angle)
        self.orienting_throttle = throttle
        self._half_orienting_angle_original_diff_abs = abs(angle-self.angle) / 2.0

        if self.debug_visuals:
            vec = Vec2d(50, 0).rotated_degrees(angle)
            self._orienting_line.points = (0, 0, vec.x, vec.y)

    def update(self, dt):
        """Called after physics space has done a step update"""

        body = self.phy_body
        # TODO drag, continuous force? how to update instead of adding new, just reset? look at arrows example

        drag_const = 0.000000001  # drag coeficcent * density of fluid
        # TODO cos/sine of angle?
        drag_force = body.velocity.rotated_degrees(180) * (body.velocity.get_length_sqrd() * self.cross_area * drag_const)
        self.phy_body.apply_impulse(drag_force)

        # Update visual position and rotation with information from physics Body
        body = self.phy_body
        x = body.position.x
        y = body.position.y

        # +counter-clockwise (axis vertical)
        self.angle = degrees(body.angle)  # adjust orientation of the widget

        for bp in self.body_parts:
            bp.update()


        # TODO Does physics system have way of bounding?
        parent = self.parent
        out_of_bounds = False
        if y > parent.height:
            y = 1
            out_of_bounds = True

        if y < 0:
            y = parent.height - 1
            out_of_bounds = True

        if x > parent.width:
            x = 1
            out_of_bounds = True

        if x < 0:
            x = parent.width - 1
            out_of_bounds = True

        if out_of_bounds:
            self.move(x, y)
        else:
            self.pos = (x, y)

        # Needed at all?
        # update_creature()



    def set_behavior(self, b):
        self.current_behavior = b
        # TODO think about this API
        b.attach(self)

# TODO PhysicsVisual baseclass?
class TentacleBodyPart():

    def __init__(self, jelly):
        mass = 20
        moment = 40
        self.phy_body = body = phy.Body(mass, moment)

        # self.phy_body.velocity_limit = 1000

        # self.radius = radius = 20
        # self.phy_shape = phy.Circle(body, radius, (0, 0))
        # phy.R
        self.half_width = width = 100
        self.half_height = height = 50

        points = [(-width, -height), (-width, height), (width, height), (width, -height)]
        moment = phy.moment_for_poly(mass, points, (0,0))
        self.phy_body = body = phy.Body(mass, moment)
        self.phy_shape = shape = phy.Poly(body, points, (0, 0))
        shape.friction = 0.4
        shape.elasticity = 0.3

        pos = Vec2d(jelly.pos) + jelly.phy_body.rotation_vector.rotated_degrees(180) * (2*width + jelly.phy_shape.radius/2.0)
        body.position = pos

        # phy.PivotJoint(jelly.phy_body, body, jelly.phy_body.position)

        # Set rest_length to current distance between attachments
        rest_length = body.position.get_distance(jelly.phy_body.position) - width
        stiffness = 100
        damping = 50
        # self.spring = phy.DampedSpring(jelly.phy_body, body, (0, 0), (width, 0), rest_length, stiffness, damping)
        self.spring1 = phy.DampedSpring(jelly.phy_body, body, (0, height), (width, height), rest_length, stiffness,
                                       damping)

        self.spring2 = phy.DampedSpring(jelly.phy_body, body, (0, -height), (width, -height), rest_length, stiffness,
                                       damping)


        # rotation acts on angle; might be useful if parts are offset


        # self.rot_spring = phy.DampedRotarySpring(jelly.phy_body, body, 0, stiffness*10, damping)
        # jelly.phy_space.add(spring)
        # max_bias, max_force?

        # canvas = Canvas(opacity=1.0)
        with jelly.canvas.after:
            Color(rgba=(0, 0, 1.0, 0.8))

            print('tent pos', pos)
            # self.ellipse = Ellipse(pos=(pos.x-radius, pos.y-radius), size=(radius*2, radius*2))
            PushMatrix()
            self._trans = Translate()
            self._rot = Rotate()
            self.rect = Rectangle(pos=(-width, -height), size=(width * 2, height * 2))
            PopMatrix()



    def update(self):
        body = self.phy_body
        # self.rect.pos = (body.position.x-self.half_width, body.position.y-self.half_height)
        self._trans.xy = (body.position.x, body.position.y)

        # +counter-clockwise (axis vertical)
        self._rot.angle = degrees(body.angle)
        # self.angle = degrees(body.angle)  # adjust orientation of the widget

    def bind_physics_space(self, space):
        space.add(self.phy_body, self.phy_shape)
        space.add(self.spring1)
        space.add(self.spring2)
        # space.add(self.rot_spring)


class Jelly(Creature):

    def __init__(self, **kwargs):

        self._bell_animator = None
        self._prev_bell_vertical_fraction = 0.0
        self.bell_push_dir = True  # whether Bell is pulsing as to push jelly
        # indices of the Bell Mesh that can be the farthest horizontally to the right
        # (used to determine the bell_diameter dynamically)
        self._rightmost_vertices_for_step = {}

        # Ideally Animation would be more abstract
        # However, this game focuses only on Jellies
        # So it's much easier to hard-code the knowledge of bell pulses, tentacle drift, etc.
        self.store = kwargs.get('jelly_store')

        super(Jelly, self).__init__(**kwargs)

        self.body_parts.append(TentacleBodyPart(self))


    def draw_creature(self):
        # called with canvas
        store = self.store

        # Draw Jelly Bell
        anim = store['bell_animation']
        mesh_mode = str(anim['mesh_mode'])
        if mesh_mode != 'triangle_fan':
            raise ValueError('Need to calc centroid in other modes')

        # first vertex to be used for centroid
        # centroid = anim['centroid']  # FUTURE: define centroid in data?
        verts = anim['steps'][setup_step]['vertices']

        # Draw centered at pos for Scale/Rotation to work correctly
        PushMatrix()

        adjustment = (-verts[0], -verts[1])
        self.centering_trans_x, self.centering_trans_y = adjustment
        Logger.debug('Jelly: centering adjustment %s', adjustment)
        # Translate(xy=adjustment)
        t = Translate()
        t.xy = adjustment

        img = CoreImage(anim['image_filepath'])
        self.bell_mesh = mesh = Mesh(mode=mesh_mode, texture=img.texture)
        a = MeshAnimator.from_animation_data(anim)
        self._bell_animator = a
        a.mesh = mesh
        a.bind(vertical_fraction=self.on_bell_vertical_fraction, step=self.on_bell_animstep)
        a.start_animation()

        PopMatrix()


        # Visualize physics shape
        # size will be set to radius in calc_bell_radius()
        if self.debug_visuals:
            Color(rgba=(0.1, 0.4, 0.5, 0.9))
            self._phys_shape_ellipse = Line(ellipse=(-5, -5, 10, 10))
                # Ellipse(pos=(-5, -5), size=(10, 10))

        # Update Physics shape
        self.calc_bell_radius()


    def calc_bell_radius(self):
        """Get the current bell radius
        Updates bell physics shape, self.cross_area, self.bell_radius
        """

        # Coordinates are in Texture image x, y coords
        x_adjustment = self.centering_trans_x  # number is negative (add to adjust)
        verts = self.bell_mesh.vertices
        rightmost_dist = 0
        for vertex_index in range(0, len(verts), 4):
            x = verts[vertex_index] + x_adjustment
            if x > rightmost_dist:
                rightmost_dist = x

        self.bell_radius = rightmost_dist
        scaled_bell_radius = rightmost_dist * self.scale
        # Updating shape is not really allowed! Need to create a new shape each time
        # self.phy_shape.radius = scaled_bell_radius
        # In some languages multiplying by self is faster than pow

        # Maybe calc moment manually instead of using function?
        # r_sqd = rightmost_dist*rightmost_dist
        # self.phy_body.moment = (pi / 2.0) * r_sqd * r_sqd
        self.phy_body.moment = phy.moment_for_circle(self.phy_body.mass, 0, scaled_bell_radius)
        self.cross_area = pi * scaled_bell_radius * scaled_bell_radius

        # Will be affected by Scale, so don't use scaled_bell_radius
        if self.debug_visuals:
            shape_radius = self.phy_shape.radius
            self._phys_shape_ellipse.ellipse = (-shape_radius, -shape_radius,
                                                shape_radius * 2.0, shape_radius * 2.0)
            # self._phys_shape_ellipse.pos = (-rightmost_dist, -rightmost_dist)
            # self._phys_shape_ellipse.size = (rightmost_dist * 2.0, rightmost_dist * 2.0)

        return rightmost_dist

    # TODO change pulse speed according to throttle
    #def orient


    def on_bell_animstep(self, meshanim, step):
        self._prev_bell_vertical_fraction = 0.0
        # Moving toward closed_bell is pushing
        self.bell_push_dir = self._bell_animator.step_names[step] == 'closed_bell'


    def on_bell_vertical_fraction(self, meshanim, frac):
        """Called every time bell animation's vertical fraction changes
        1.0 is up and open all the way
        0.0 is down and closed all the way
        """

        body = self.phy_body
        rot_vector = body.rotation_vector

        # Difference in the vertical_fraction from last call
        # Always positive since fraction always moves from 0.0 to 1.0
        v_diff = frac - self._prev_bell_vertical_fraction

        radius = self.calc_bell_radius()

        # Lots of little impulses? Or use forces?
        # impulse i think, since could rotate and would need to reset_forces and calc new each time anyway

        # TODO forces when going backwords? yes? adjust by fraction
        # hz_fraction = self._bell_animator.horizontal_fraction

        #self.phy_body.activate()
        # power = (5000 if self.bell_push_dir else -500) * v_diff
        # impulse = Vec2d(0, 1) * power
        push_factor = 0.1
        power = self.cross_area * v_diff * (push_factor if self.bell_push_dir else -push_factor)


        # Apply impulse off-center to rotate
        # Positive rotates clockwise
        offset_dist = 0
        if self.orienting:
            angle_diff = self.orienting_angle - self.angle
            # TODO use orienting_throttle
            offset_dist = radius * 0.2
            if angle_diff > 0:
                offset_dist *= -1

            # Need to kill angular velocity before reaching the angle
            # One way is to measure the time it takes to reach halfway, and then reverse thrust....
            # However this is brittle if the Jelly already has angular velocity from another source
            # Instead, want to calculate when to reverse offset_dist based on how much torque it can apply
            # But this is even more difficult because the impulse is not constant, so back to time based...

            # TODO ...and angular velocity is towards orienting_angle?
            abs_angle_diff = abs(angle_diff)
            # FIXME if for some reason, does not have enough angular velocity, this would cause
            # an oscillation around an angle without ever reaching target orienting angle
            # if abs_angle_diff <= self._half_orienting_angle_original_diff_abs:
                # Start reducing angular velocity
                # print('reducing angular velocity %f'%body.angular_velocity)
                # offset_dist *= -1

            # TODO end orieting
            # if abs_angle_diff < 1.0 and body.angular_velocity < x:
                #self.orienting = False


        if offset_dist:
            # if offset is static, it keeps oscillating
            # https://chipmunk-physics.net/forum/viewtopic.php?f=1&t=59
            # The offset is in world space coordinates, but is relative to the center of gravity of the body. This means that an r of (0,2) will always be 2 units above the center of gravity in world space coordinates. The offset does not rotate with the body.
            # offset = self.phy_body.local_to_world(Vec2d(50, 0))

            self.phy_body.apply_impulse(rot_vector * power, rot_vector.perpendicular() * offset_dist)

        else:
            self.phy_body.apply_impulse(rot_vector * power)

        # self.phy_body.apply_impulse(self.phy_body.rotation_vector * power, (offset['x'], offset['y']))

        # self.phy_body.apply_impulse(impulse.rotated(self.phy_body.angle))

        #print("Velocity %s  positions %s" %(self.phy_body.velocity, self.phy_body.position))

        self._prev_bell_vertical_fraction = frac


    # TODO thing about what is controled in MeshAnimation vs Creature
    def bell_pulse_complete(self, anim_seq, widget):
        # Schedule next pulse
        Clock.schedule_once(self.animate_bell, random.triangular(0.3, 2.0, 0.5))
        raise AssertionError('not used?')


    # def update_creature(self):
    #     pass

    # FIXME Old code: React to size or not?
    # def on_size(self, widget, new_size):
    #     if hasattr(self, '_mesh_scale'):
    #         # Scale the Mesh relative to the Image size vertices were created with
    #         self._mesh_scale.xyz = (new_size[0] / self.texture_img.width, new_size[1] / self.texture_img.height, 1)
    #
    #     if hasattr(self, '_mesh_trans'):
    #         # flip_vertical correction needs to update Translate when height changes
    #         self._mesh_trans.y = new_size[1]
    #
    # def on_scale(self, widget, new_scale):
    #     self.size = (self.texture_img.width * self.scale, self.texture_img.height * self.scale)
