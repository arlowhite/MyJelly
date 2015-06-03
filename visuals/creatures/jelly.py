__author__ = 'awhite'

# Body parts that make up Jelly Creature
# DO NOT Rename or Move any classes from here as the class path is serialized

import random
from math import cos, sin, radians, degrees, pi

from kivy.logger import Logger
from kivy.graphics import Color, Translate, PushMatrix, PopMatrix, \
    Mesh, Ellipse, Line
from kivy.core.image import Image as CoreImage
from kivy.clock import Clock

import cymunk as phy
from cymunk import Vec2d

from animations import MeshAnimator, setup_step
from misc.exceptions import InsufficientData
from misc.util import not_none_keywords
from .creature import Creature

# TODO PhysicsVisual baseclass?
class GooeyBodyPart(object):
    """Creates a Mesh that behaves as gooey mass by creating physical springs between all vertices
    and stiffer center skeleton"""

    class_path = 'visuals.creatures.jelly.GooeyBodyPart'

    @staticmethod
    def create_construction_structure(anim_constr_screen):
        anim_constr = anim_constr_screen.ids.animation_constructor
        vertices, indices = anim_constr.calc_mesh_vertices(update_mesh=False)

        return {GooeyBodyPart.class_path:
                {
                    'image_filepath': anim_constr.image_filepath,
                    'mesh_mode': anim_constr.mesh_mode,
                    'vertices': vertices, 'indices': indices
                }
            }

    @staticmethod
    def setup_anim_constr(anim_constr_screen, structure):
        """Modify the AnimationConstructor to represent the state stored in the
        structure (as returned from create_construction_structure)
        """

        anim_constr = anim_constr_screen.ids.animation_constructor
        # with disables animation while changing data
        with anim_constr:
            data = structure[GooeyBodyPart.class_path]
            anim_constr_screen.image_filepath = data['image_filepath']
            anim_constr.image_filepath = data['image_filepath']
            anim_constr.mesh_mode = data['mesh_mode']
            anim_constr.setup_control_points(data['vertices'])

    @not_none_keywords('creature', 'image_filepath', 'vertices', 'indices')
    def __init__(self, creature=None, image_filepath=None, mesh_mode='triangle_fan',
                 vertices=None, indices=None,
                 mass=100, stiffness=10, damping=5):

        if len(vertices) < 3:
            raise InsufficientData('Less than 3 vertices')
        if len(indices) < 3:
            raise InsufficientData('Less than 3 indices')

        mesh_mode = str(mesh_mode)  # Mesh.mode does not support unicode
        if mesh_mode != 'triangle_fan':
            raise ValueError('Other mesh_modes not supported; need to calc centroid in other modes')

        # FIXME minimize assupmtions about what binding to
        self.jelly = creature

        creature_phy_body = creature.phy_body

        # backwards unit vector
        backwards_vec = creature_phy_body.rotation_vector.rotated_degrees(180)
        jelly_pos = Vec2d(creature.pos)
        # +  * (2 * width + jelly.phy_shape.radius / 2.0)

        canvas_after = creature.canvas.after

        stiffness = 10
        damping = 5
        creature_radius = creature.phy_shape.radius  # FIXME assumes Circle shape

        # Mass
        tentacles_total_mass = 0.5 * creature_phy_body.mass
        center_chain_mass = 0.5 * tentacles_total_mass
        outer_chain_mass = tentacles_total_mass - center_chain_mass

        ### Outer Chain ###
        # TODO Prevent Mesh triangles from flipping somehow
        canvas_after.add(Color(rgba=(1.0, 0, 0, 0.3)))

        # FIXME Tentacles vertices don't need all this encoding
        positions = []

        # Mesh vertices translated to correct world positions relative to Jelly
        # will set Mesh.vertices at end
        translated_vertices = []

        # Start at 4 to skip centroid
        tentacles_offset = backwards_vec * -1.0
        for i in range(4, len(vertices), 4):
            # within canvas to scale...
            # These are in Image coordinates
            # Can't just scale and rotate because it's attached to the physics system

            xy = creature.texture_xy_to_world(vertices[i], vertices[i+1]) + tentacles_offset
            positions.append(xy)
            translated_vertices.extend((xy.x, xy.y, vertices[i+2], vertices[i+3]))

        self.outer_chain = outer_chain = self._create_chain(positions, canvas_after, loop_around=True,
                                                            mass=outer_chain_mass/len(positions))

        closest_stiffness = 1000
        closest_damping = 500
        # Left Offset
        offset = (0, creature_radius*0.5)
        offset_world_vec = Vec2d(offset).rotated_degrees(creature.angle) + jelly_pos
        # with canvas_after:
        #     Rectangle(pos=(offset_world_vec.x, offset_world_vec.y), size=(10, 10))
        # offset_vec = jelly_pos + backwards_vec.perpendicular() * (0.5 * jelly_radius)

        # Get closest to offset in outer chain
        closest = min(outer_chain, key=lambda x: x[0].body.position.get_distance(offset_world_vec))
        closest_body = closest[0].body
        rest_length = offset_world_vec.get_distance(closest_body.position)
        spring = phy.DampedSpring(creature_phy_body, closest_body, offset, (0, 0),
                                  rest_length, closest_stiffness, closest_damping)
        closest[2].append(spring)

        # FIXME Setup groups some other way, Need to detect points that start inside
        closest[0].group = creature.phy_group_num

        # Right Offset
        offset = (0, -creature_radius*0.5)
        offset_world_vec = Vec2d(offset).rotated_degrees(creature.angle) + jelly_pos
        # with canvas_after:
        #     Rectangle(pos=(offset_world_vec.x, offset_world_vec.y), size=(10, 10))
        # offset_vec = jelly_pos + backwards_vec.perpendicular() * (0.5 * jelly_radius)

        # Get closest to offset in outer chain
        closest = min(outer_chain, key=lambda x: x[0].body.position.get_distance(offset_world_vec))
        closest_body = closest[0].body
        rest_length = offset_world_vec.get_distance(closest_body.position)
        spring = phy.DampedSpring(creature_phy_body, closest_body, offset, (0, 0),
                                  rest_length, closest_stiffness, closest_damping)
        closest[2].append(spring)

        # FIXME Setup groups some other way, Need to detect points that start inside
        closest[0].group = creature.phy_group_num


        ### Center Chain ###
        canvas_after.add(Color(rgba=(0, 0, 1.0, 0.3)))
        radius = 12
        dist_apart = 3 * radius  # rest length
        start = jelly_pos + backwards_vec * (creature.phy_shape.radius + 20)
        positions = [start + backwards_vec * (dist_apart * n) for n in range(2)]


        self.center_chain = center_chain = self._create_chain(positions, canvas_after,
                                                              radius=radius, mass=center_chain_mass / len(positions),
                                                              stiffness=stiffness * 10, damping=damping * 10)

        first = center_chain[0]
        rest_length = creature_phy_body.position.get_distance(first[0].body.position)
        spring = phy.DampedSpring(creature_phy_body, first[0].body, (0, 0), (0, 0),
                                  rest_length, stiffness, damping)
        first[2].append(spring)

        # Link outer chain with center
        self._cross_link(outer_chain, center_chain, stiffness=stiffness*1.0, damping=damping*1.0)

        self.chains = (center_chain, outer_chain)


        # Setup Mesh


        # triangle_fan needs centroid
        # TODO Use centroid? Make centroid it's own massive point? single point in center_chain?
        # FIXME Really hackish, but just using first center chain for now with original u, v
        cent_pos = center_chain[0][0].body.position
        # Prepend centroid vertices list
        translated_vertices = [cent_pos.x, cent_pos.y, vertices[2], vertices[3]] + translated_vertices

        with creature.canvas.before:
            Color(rgba=(1.0, 1.0, 1.0, 1.0))
            img = CoreImage(image_filepath)
            self.mesh = mesh = Mesh(mode=mesh_mode, texture=img.texture, indices=indices,
                                    vertices=translated_vertices)

        creature.add_body_part(self)


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

    def _create_chain(self, positions, canvas, mass=1, radius=10, loop_around=False, stiffness=50, damping=15):

        prev = None

        assert len(positions) > 0

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

        # Force visual update
        self.update()

class JellyBell(Creature):
    """An animated Jelly bell Creature that uses a MeshAnimator to animate between an open
    and closed position. Applies physics forces in proportion with Bell animation.
    Also induces drag."""
    # Ideally Animation would be more abstract
    # However, this game focuses only on Jellies
    # So it's much easier to hard-code the knowledge of bell pulses, tentacle drift, etc.

    class_path = 'visuals.creatures.jelly.JellyBell'

    @not_none_keywords('image_filepath', 'mesh_animator')
    def __init__(self, image_filepath=None, mesh_animator=None, **kwargs):
        """Creates Mesh using image_filepath and binds MeshAnimator to it

        image_filepath"""

        self.image_filepath = image_filepath
        self.mesh_animator = mesh_animator

        self._prev_bell_vertical_fraction = 0.0
        self.bell_push_dir = True  # whether Bell is pulsing as to push jelly
        # indices of the Bell Mesh that can be the farthest horizontally to the right
        # (used to determine the bell_diameter dynamically)
        self._rightmost_vertices_for_step = {}

        super(JellyBell, self).__init__(**kwargs)

        mesh_animator.bind(vertical_fraction=self.on_bell_vertical_fraction, step=self.on_bell_animstep)
        mesh_animator.start_animation()

        # super called draw_creature

    @staticmethod
    # FIXME verify screen or not, check calls
    def create_construction_structure(anim_constr_screen):
        """Creates construction structure see: construct_value()
        from AnimationConstructor state.
        """
        anim_constr = anim_constr_screen.ids.animation_constructor

        return {JellyBell.class_path:
                    {'image_filepath': anim_constr_screen.image_filepath,
                    'mesh_animator': anim_constr.create_mesh_animator_construction()}}

    @staticmethod
    def setup_anim_constr(anim_constr_screen, structure):
        """Modify the AnimationConstructor to represent the state stored in the
        structure (as returned from create_construction_structure)
        """

        # This seems like the best way to keep deserialization/serialization code
        # together and associated with the Class.
        # Could construct the value and read from JellyBell, MeshAnimator,
        # but this is just as tedious and wasteful

        anim_constr = anim_constr_screen.ids.animation_constructor
        # with disables animation while changing data
        with anim_constr:
            data = structure[JellyBell.class_path]
            anim_constr_screen.image_filepath = data['image_filepath']
            anim_constr.image_filepath = data['image_filepath']
            mesh_animator_structure = data['mesh_animator'][MeshAnimator.class_path]
            anim_constr.mesh_mode = mesh_animator_structure['mesh_mode']
            anim_constr.setup_control_points(mesh_animator_structure['initial_vertices'])

            for step_structure in mesh_animator_structure['steps']:
                anim_constr.add_step(step_structure['step_name'], step_structure['vertices'])


    def texture_xy_to_world(self, x, y):
        # position + adjustment + x|y
        vec = Vec2d(x + self.centering_trans_x, y + self.centering_trans_y)
        vec.rotate_degrees(self.angle - 90)
        return vec + Vec2d(*self.pos)


    def draw_creature(self):
        if hasattr(self, 'bell_mesh'):
            raise AssertionError('Already called draw_creature!')

        # Draw Jelly Bell

        a = self.mesh_animator
        verts = a.initial_vertices

        # first vertex to be used for centroid
        if a.mesh_mode != 'triangle_fan':
            raise AssertionError('Need centroid to recenter JellyBell')

        # Draw centered at pos for Scale/Rotation to work correctly
        PushMatrix()

        adjustment = (-verts[0], -verts[1])
        self.centering_trans_x, self.centering_trans_y = adjustment
        Logger.debug('Jelly: centering adjustment %s', adjustment)
        # Translate(xy=adjustment)
        t = Translate()
        t.xy = adjustment

        img = CoreImage(self.image_filepath)
        self.bell_mesh = mesh = Mesh(texture=img.texture)
        a.mesh = mesh

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
        self.bell_push_dir = self.mesh_animator.step_names[step] == 'closed_bell'


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

        push_factor = 0.2
        power = self.cross_area * v_diff * (push_factor if self.bell_push_dir else -0.8 * push_factor)


        # Apply impulse off-center to rotate
        # Positive rotates clockwise
        offset_dist = 0
        if self.orienting:
            angle_diff = self.orienting_angle - self.angle

            # TODO use orienting_throttle
            offset_dist = radius * 0.3
            if angle_diff > 0:
                offset_dist *= -1

            # Need to kill angular velocity before reaching the angle
            # One way is to measure the time it takes to reach halfway, and then reverse thrust....
            # However this is brittle if the Jelly already has angular velocity from another source
            # Instead, want to calculate when to reverse offset_dist based on how much torque it can apply
            # But this is even more difficult because the impulse is not constant, so back to time based...

            # TODO ...and angular velocity is towards orienting_angle?
            abs_angle_diff = abs(angle_diff)

            if abs_angle_diff < 45:
                offset_dist *= abs_angle_diff/ 45.0

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
