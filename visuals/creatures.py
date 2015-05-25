__author__ = 'awhite'

import random
from math import cos, sin, radians, degrees, pi

from kivy.logger import Logger
from kivy.graphics import Rectangle, Triangle, Color, Rotate, Translate, InstructionGroup, PushMatrix, PopMatrix, \
    PushState, PopState, Canvas, Mesh, Scale, Ellipse, Line, ClearColor
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
from misc.exceptions import InsufficientData


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
class Creature(object):
    """Visual entity that moves around (update called on game tick)
     and is attached to the Cymunk physics system"""

    def __init__(self, **kwargs):

        self.debug_visuals = True  # TODO control with global config

        self.parent = kwargs.get('parent', None)  # FIXME remove? shouldn't be aware of parent widget

        self.orienting = False  # is currently orienting toward orienting_angle
        self.orienting_angle = 0
        self.orienting_throttle = 1.0

        # TODO just use a global for all creatures?
        self.phy_group_num = kwargs.get('phy_group_num', 0)

        # TODO think about scaling mass volume cubic?
        mass = 1e5  # mass of the body i.e. linear moving inertia
        moment = 1e5  # moment of inertia, i.e. rotation inertia
        mass = 100
        self.phy_body = body = phy.Body(mass, moment)
        self.phy_body.velocity_limit = 1000

        # Composite body parts that update every tick
        self.body_parts = []

        #box = phy.Poly.create_box(body, size=(200, 100))
        radius = 100
        self.phy_shape = phy.Circle(body, radius, (0, 0))
        self.phy_shape.friction = 0.4
        self.phy_shape.elasticity = 0.3
        self.phy_shape.group = self.phy_group_num
        #body.position = 400, 100  # set some position of body in simulated space coordinates

        # Set properties that will be used within draw()
        # pos and angle are stored in the physics objects
        body.position = kwargs.get('pos', (0, 0))
        body.angle = radians(self.angle)

        self.canvas = Canvas()

        self.draw()

        # Scale is stored in Scale() object
        self.scale = kwargs.get('scale', 1.0)


    # Attributes API used externally
    # Internally Physics body objects are directly referenced
    @property
    def pos(self):
        """Returns Vec2d of physics body position"""
        # TODO Leaking Vec2d type, but I don't think I care
        return self.phy_body.position

    @pos.setter
    def pos(self, newpos):
        old_pos = Vec2d(self.phy_body.position)

        self.phy_body.position = newpos

        # Move body parts as well
        # TODO actually move body part visual as well instead of relying on update() to do it
        move_diff_vec = self.phy_body.position - old_pos
        for bp in self.body_parts:
            bp.translate(move_diff_vec)

        self._translate.xy = newpos


    # Note: Cymunk does not modulo the angle and it can also be negative
    # Think about the best way to deal with angle diffs...
    # 5 - 355 = -350. Could +360 if < 0, but there must be an easier way.
    # Maybe using vectors is better? angle between vectors? dot products?
    @property
    def angle(self):
        """Get the current angle of the PhysicsEntity in degrees from -180 to 180
        0 degrees is to the right.
        """

        return fix_angle(degrees(self.phy_body.angle))

    @angle.setter
    def angle(self, newangle):
        "Set the angle in degrees"
        newangle = radians(newangle)
        self.phy_body.angle = newangle
        self._rotate.angle = newangle - 90

    @property
    def scale(self):
        return self._scale.x

    @scale.setter
    def scale(self, scale):
        # TODO what does z do for 2D?
        self._scale.xyz = (scale, scale, 1.0)


    def bind_physics_space(self, space):
        '''Attach to the given physics space'''
        space.add(self.phy_body, self.phy_shape)  # add physical objects to simulated space
        #self.phy_body.activate()

        for bp in self.body_parts:
            bp.bind_physics_space(space)

    def draw(self):
        # with self.canvas.before:
        #     PushMatrix()
        #     PushState()
        #
        # with self.canvas.after:
        #     PopMatrix()
        #     PopState()


        with self.canvas:
            PushMatrix()
            PushState()

            self._color = Color(1, 1, 1, 1)

            # Control size without recalculating vertices
            self._scale = Scale(1, 1, 1)

            # Translate graphics to Creature's position
            self._translate = Translate()
            self._translate.xy = self.pos

            if self.debug_visuals:
                # Need to undo rotation when drawing orienting line
                PushMatrix()

            self._rotate = Rotate()
            self._rotate.angle = self.angle - 90

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

            PopMatrix()
            PopState()






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

        # Optimization: Set angle and pos on phy_body directly to avoid extra function execution
        body = self.phy_body

        # 1. Apply forces to body
        # TODO drag, continuous force? how to update instead of adding new, just reset? look at arrows example

        drag_const = 0.0000000001  # drag coeficcent * density of fluid
        # TODO cos/sine of angle?
        drag_force = body.velocity.rotated_degrees(180) * (body.velocity.get_length_sqrd() * self.cross_area * drag_const)
        self.phy_body.apply_impulse(drag_force)

        # Update visual position and rotation with information from physics Body


        # +counter-clockwise (axis vertical)
        self._rotate.angle = degrees(body.angle) - 90 # adjust orientation graphics

        # Update body parts
        for bp in self.body_parts:
            bp.update()


        # Check if in bounds, wrap to other side if out
        # TODO Bounding shouldn't be in this Class
        x = body.position.x
        y = body.position.y

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
            # Trigger move of main body and body-parts
            self.pos = (x, y)
        else:
            self._translate.xy = (x, y)


        # Needed at all?
        # update_creature()


    # TODO this should be done differently, think about AOP/Component oriented programming
    def set_behavior(self, b):
        self.current_behavior = b
        # TODO think about this API
        b.attach(self)

# TODO PhysicsVisual baseclass?
class TentacleBodyPart():

    def __init__(self, jelly):

        self.jelly = jelly

        try:
            anim = jelly.store['tentacles']
            anim_setup = anim['steps']['__setup__']
        except KeyError as ex:
            raise InsufficientData(repr(ex))


        # 3 lines of circles
        # center line a bit stiffer and more massive


        backwards_vec = jelly.phy_body.rotation_vector.rotated_degrees(180)
        jelly_pos = Vec2d(jelly.pos)
        # +  * (2 * width + jelly.phy_shape.radius / 2.0)


        canvas_after = jelly.canvas.after
        canvas_after.add(Color(rgba=(0, 0, 1.0, 0.3)))

        stiffness = 10
        damping = 5
        tentacles_total_mass = 0.8 * jelly.phy_body.mass

        radius = 12
        dist_apart = 3 * radius  # rest length
        start = jelly_pos + backwards_vec * (jelly.phy_shape.radius + 20)
        positions = [start + backwards_vec * (dist_apart * n) for n in range(2)]

        center_chain_mass = 0.5 * tentacles_total_mass
        outer_chain_mass = tentacles_total_mass - center_chain_mass
        self.center_chain = center_chain = self._create_chain(positions, canvas_after,
                                                              radius=radius, mass=center_chain_mass/len(positions))

        first = center_chain[0]
        rest_length = jelly.phy_body.position.get_distance(first[0].body.position)
        spring = phy.DampedSpring(jelly.phy_body, first[0].body, (0, 0), (0, 0),
                                  rest_length, stiffness, damping)
        first[2].append(spring)

        jelly_radius = jelly.phy_shape.radius

        canvas_after.add(Color(rgba=(1.0, 0, 0, 0.3)))

        # self._cross_link(right_chain, center_chain)
        # FIXME Tentacles vertices don't need all this encoding
        positions = []

        vertices = anim_setup['vertices']
        if len(vertices) < 3:
            raise InsufficientData('Only %d tentacle vertices'%len(vertices))

        # TODO Make centroid it's own massive point? single point in center_chain?
        translated_vertices = []
        # FIXME Really hackish, but just using first center chain for now with original u, v
        cent_pos = center_chain[0][0].body.position
        translated_vertices.extend((cent_pos.x, cent_pos.y, vertices[2], vertices[3]))

        # Start at 4 to skip centroid
        tentacles_offset = backwards_vec * -30.0
        for i in range(4, len(vertices), 4):
            # within canvas to scale...
            # These are in Image coordinates
            # Can't just scale and rotate because it's attached to the physics system

            xy = jelly.texture_xy_to_world(vertices[i], vertices[i+1]) + tentacles_offset
            positions.append(xy)
            translated_vertices.extend((xy.x, xy.y, vertices[i+2], vertices[i+3]))

        self.outer_chain = outer_chain = self._create_chain(positions, canvas_after, loop_around=True,
                                                            mass=outer_chain_mass/len(positions))

        closest_stiffness = 1000
        closest_damping = 500
        # Left Offset
        offset = (0, jelly_radius*0.5)
        offset_world_vec = Vec2d(offset).rotated_degrees(jelly.angle) + jelly_pos
        # with canvas_after:
        #     Rectangle(pos=(offset_world_vec.x, offset_world_vec.y), size=(10, 10))
        # offset_vec = jelly_pos + backwards_vec.perpendicular() * (0.5 * jelly_radius)

        # Get closest to offset in outer chain
        closest = min(outer_chain, key=lambda x: x[0].body.position.get_distance(offset_world_vec))
        closest_body = closest[0].body
        rest_length = offset_world_vec.get_distance(closest_body.position)
        spring = phy.DampedSpring(jelly.phy_body, closest_body, offset, (0, 0),
                                  rest_length, closest_stiffness, closest_damping)
        closest[2].append(spring)

        # FIXME Setup groups some other way, Need to detect points that start inside
        closest[0].group = jelly.phy_group_num

        # Right Offset
        offset = (0, -jelly_radius*0.5)
        offset_world_vec = Vec2d(offset).rotated_degrees(jelly.angle) + jelly_pos
        # with canvas_after:
        #     Rectangle(pos=(offset_world_vec.x, offset_world_vec.y), size=(10, 10))
        # offset_vec = jelly_pos + backwards_vec.perpendicular() * (0.5 * jelly_radius)

        # Get closest to offset in outer chain
        closest = min(outer_chain, key=lambda x: x[0].body.position.get_distance(offset_world_vec))
        closest_body = closest[0].body
        rest_length = offset_world_vec.get_distance(closest_body.position)
        spring = phy.DampedSpring(jelly.phy_body, closest_body, offset, (0, 0),
                                  rest_length, closest_stiffness, closest_damping)
        closest[2].append(spring)

        # FIXME Setup groups some other way, Need to detect points that start inside
        closest[0].group = jelly.phy_group_num

        self._cross_link(outer_chain, center_chain, stiffness=stiffness*0.1, damping=damping*0.1)

        self.chains = (center_chain, outer_chain)


        # Setup Mesh

        mesh_mode = str(anim['mesh_mode'])
        if mesh_mode != 'triangle_fan':
            raise ValueError('Need to calc centroid in other modes')

        with jelly.canvas.before:
            Color(rgba=(1.0, 1.0, 1.0, 1.0))
            img = CoreImage(anim['image_filepath'])
            indices = anim['indices']
            self.mesh = mesh = Mesh(mode=mesh_mode, texture=img.texture, indices=indices,
                                    vertices=translated_vertices)


    def _cross_link(self, chain1, chain2, stiffness=20, damping=10):
        "create springs with closest two points from the other chain"

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

    def _create_chain(self, positions, canvas, mass=1, radius=10, loop_around=False):

        stiffness = 50
        damping = 15
        prev = None

        mypos = self.jelly.phy_body.position
        farthest_dist = max(pos.get_distance(mypos) for pos in positions)

        center_chain = []
        for pos in positions:
            # mass falls with distance from jelly
            dist = mypos.get_distance(pos)
            m = mass * (dist / farthest_dist)**2.0 + 0.2 * mass

            moment = phy.moment_for_circle(m, 0, radius)
            body = phy.Body(m, moment)
            shape = phy.Circle(body, radius)
            shape.friction = 0.4
            shape.elasticity = 0.3
            body.position = pos
            Logger.debug("Creating chain body mass=%s position=%s radius=%s", m, pos, radius)

            e = Ellipse(pos=(body.position.x - radius, body.position.y - radius), size=(radius * 2.0, radius * 2.0))
            canvas.add(e)

            springs = []
            if prev:
                # attach spring to previous
                dist_apart = prev[0].body.position.get_distance(body.position)
                spring = phy.DampedSpring(prev[0].body, body, (0, 0), (0, 0), dist_apart, stiffness,
                                          damping)
                springs.append(spring)

            item = (shape, e, springs)
            center_chain.append(item)

            prev = item

        if loop_around:
            last_body = body
            body = center_chain[0][0].body
            dist_apart = last_body.position.get_distance(body.position)
            spring = phy.DampedSpring(last_body, body, (0, 0), (0, 0),
                                      dist_apart, stiffness, damping)
            center_chain[0][2].append(spring)

        return center_chain


        self.update()



    def update(self):

        for chain in self.chains:
            for shape, drawn_ellipse, spring in chain:
                body = shape.body
                drawn_ellipse.pos = body.position.x - shape.radius, body.position.y - shape.radius

                # drag force
                # FIXME High drag is warping out Jellies !?
                drag_force = body.velocity.rotated_degrees(180) * (body.velocity.get_length_sqrd() * 0.000001)
                body.apply_impulse(drag_force)


        # Update Mesh vertices
        verts = self.mesh.vertices
        x = 0.0
        y = 0.0
        for i, item in enumerate(self.outer_chain):
            pos = item[0].body.position
            verts[4+i*4] = pos.x
            verts[4+1+i*4] = pos.y

            x += pos.x
            y += pos.y

        # Centroid
        verts[0] = x / len(self.outer_chain)
        verts[1] = y / len(self.outer_chain)
        # pos = self.center_chain[0][0].body.position
        # verts[0] = pos.x
        # verts[1] = pos.y

        # Just average all points

        self.mesh.vertices = verts


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
        self.jelly_id = self.store['info']['id']

        super(Jelly, self).__init__(**kwargs)

        # super called draw_creature

        try:
            self.body_parts.append(TentacleBodyPart(self))
        except KeyError:
            Logger.info('%s has no tentacles information', self.jelly_id)

    def texture_xy_to_world(self, x, y):
        # position + adjustment + x|y
        vec = Vec2d(x + self.centering_trans_x, y + self.centering_trans_y)
        vec.rotate_degrees(self.angle - 90)
        return vec + Vec2d(*self.pos)


    def draw_creature(self):
        if hasattr(self, 'bell_mesh'):
            raise AssertionError('Already called draw_creature!')

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
        push_factor = 0.5
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
