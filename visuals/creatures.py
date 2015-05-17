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
        move_diff_vec = self.phy_body.position - old_pos
        for bp in self.body_parts:
            bp.translate(move_diff_vec)

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
        # I think this is due to Jelly being drawn vertically, but need to think about how to code this correction best
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

        drag_const = 0.0000000001  # drag coeficcent * density of fluid
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

        self.jelly = jelly


        # 3 lines of circles
        # center line a bit stiffer and more massive



        backwards_vec = jelly.phy_body.rotation_vector.rotated_degrees(180)
        jelly_pos = Vec2d(jelly.pos)
        # +  * (2 * width + jelly.phy_shape.radius / 2.0)


        canvas_after = jelly.canvas.after
        canvas_after.add(Color(rgba=(0, 0, 1.0, 0.8)))

        stiffness = 100
        damping = 50

        start = jelly_pos + backwards_vec * (jelly.phy_shape.radius + 20)
        self.center_chain = center_chain = self._create_chain(5, start, backwards_vec, canvas_after, mass=2)
        first = center_chain[0]
        rest_length = jelly.phy_body.position.get_distance(first[0].body.position)
        spring = phy.DampedSpring(jelly.phy_body, first[0].body, (0, 0), (0, 0),
                                  rest_length, stiffness, damping)
        first[2].append(spring)

        jelly_radius = jelly.phy_shape.radius

        canvas_after.add(Color(rgba=(1.0, 0, 0, 0.8)))
        # world pos
        left_offset = jelly_pos + backwards_vec.perpendicular() * (jelly_radius * 0.6)
        left_start = left_offset + backwards_vec * jelly_radius
        left_chain = self._create_chain(5, left_start, backwards_vec, canvas_after)
        first = left_chain[0]
        rest_length = left_offset.get_distance(first[0].body.position)
        offset = left_offset - jelly_pos
        spring = phy.DampedSpring(jelly.phy_body, first[0].body, (offset.x, offset.y), (0, 0),
                                  rest_length, stiffness, damping)
        first[2].append(spring)

        canvas_after.add(Color(rgba=(0, 1.0, 0, 0.8)))
        right_offset = jelly_pos + backwards_vec.perpendicular().rotated_degrees(180) * (jelly_radius * 0.6)
        right_start = right_offset + backwards_vec * jelly_radius
        right_chain = self._create_chain(5, right_start, backwards_vec, canvas_after)
        first = right_chain[0]
        rest_length = right_offset.get_distance(first[0].body.position)
        offset = right_offset - jelly_pos
        spring = phy.DampedSpring(jelly.phy_body, first[0].body, (offset.x, offset.y), (0, 0),
                                  rest_length, stiffness, damping)
        first[2].append(spring)

        self._cross_link(left_chain, center_chain)
        self._cross_link(right_chain, center_chain)

        self.chains = (left_chain, center_chain, right_chain)

    def _cross_link(self, chain1, chain2):
        "create springs with closest two points from the other chain"

        stiffness = 20
        damping = 5

        for shape, _, springs in chain1:
            # get closest 2 points in other chain
            # construct list of 2 element touples (dist, body)
            others = []
            for shape2, _, _ in chain2:
                others.append((shape.body.position.get_distance(shape2.body.position), shape2.body))

            others.sort(key=lambda x: x[0])

            # Springs with first two
            for x in (0, 1):
                dist, body = others[x]
                spring = phy.DampedSpring(shape.body, body, (0, 0), (0, 0),
                                          dist, stiffness, damping)

                springs.append(spring)





    def _create_chain(self, num, starting_pos, along_vector, canvas, mass = 1, radius = 10):

        dist_apart = 5 * radius  # rest length

        stiffness = 50
        damping = 15


        center_chain = []
        for n in range(num):
            moment = phy.moment_for_circle(mass, 0, radius)
            body = phy.Body(mass, moment)
            shape = phy.Circle(body, radius)
            shape.friction = 0.4
            shape.elasticity = 0.3
            body.position = starting_pos + along_vector * (dist_apart * n)

            e = Ellipse(pos=(body.position.x - radius, body.position.y - radius), size=(radius * 2.0, radius * 2.0))
            canvas.add(e)

            springs = []
            if n > 0:
                # attach spring to previous
                spring = phy.DampedSpring(center_chain[n - 1][0].body, body, (0, 0), (0, 0), dist_apart, stiffness,
                                          damping)
                springs.append(spring)

            center_chain.append((shape, e, springs))

            mass *= 0.8

        return center_chain


        self.update()



    def update(self):
        for chain in self.chains:
            for shape, drawn_ellipse, spring in chain:
                body = shape.body
                drawn_ellipse.pos = body.position.x - shape.radius, body.position.y - shape.radius

                # drag force
                drag_force = body.velocity.rotated_degrees(180) * (body.velocity.get_length_sqrd() * 0.000001)
                body.apply_impulse(drag_force)

        # make sure center chain isn't too out of whack
        # couldn't find constraints to do this for me
        jelly_body = self.jelly.phy_body
        first_body = self.center_chain[0][0].body
        vec_to_jelly = jelly_body.position - first_body.position
        angle_diff = jelly_body.rotation_vector.get_angle_between(vec_to_jelly)
        #print(angle_diff)
        force = vec_to_jelly.perpendicular_normal() * (angle_diff * 20)
        first_body.apply_impulse(force)





    def bind_physics_space(self, space):
        # space.add(self.phy_body, self.phy_shape)
        # space.add(self.spring1)
        # space.add(self.spring2)
        # space.add(self.rot_spring)

        for chain in self.chains:
            for shape, drawn_ellipse, spring in chain:
                space.add(shape.body, shape)
                space.add(spring)

    def translate(self, translation_vector):
        for chain in self.chains:
            for shape, drawn_ellipse, spring in chain:
                shape.body.position += translation_vector



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
        push_factor = 0.2
        power = self.cross_area * v_diff * (push_factor if self.bell_push_dir else -0.8*push_factor)


        # Apply impulse off-center to rotate
        # Positive rotates clockwise
        offset_dist = 0
        if self.orienting:
            angle_diff = self.orienting_angle - self.angle
            # TODO use orienting_throttle
            offset_dist = radius * 0.5
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
