__author__ = 'awhite'

from math import cos, sin, radians, degrees, pi
from weakref import ref as weakref_ref

from kivy.logger import Logger
from kivy.graphics import Rectangle, Triangle, Color, Rotate, Translate, PushMatrix, PopMatrix, \
    PushState, PopState, Canvas, Scale, Line
from kivy.event import EventDispatcher
from kivy.properties import NumericProperty, BoundedNumericProperty, BooleanProperty
from kivy.metrics import mm, dp

import cymunk as phy
from cymunk import Vec2d

from misc.util import not_none_keywords


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


# TODO Scale creature
# Different environment aspects? bounce vs teleport, etc

# Single animation update loop instead of Animation Clocks for each? or chain Animations? &=
class Creature(EventDispatcher):
    """Visual entity that moves around (update called on game tick)
     and is attached to the Cymunk physics system"""

    mass = NumericProperty(1.0e6)

    @not_none_keywords('creature_id', 'part_name')
    def __init__(self, creature_id=None, part_name=None, tweaks=None, debug_visuals=False, **kwargs):

        super(Creature, self).__init__(**kwargs)

        self.creature_id = creature_id
        self.part_name = part_name

        # All creatures will have a tweaks dictionary of various values that
        # change behaviour
        if tweaks is None:
            tweaks = {}

        if hasattr(self.__class__, 'tweaks_defaults'):
            # The Creature class should contain
            tweaks_defaults = self.__class__.tweaks_defaults

            if __debug__:
                # Warn about any tweaks passed in that have no defaults
                no_default = set(tweaks.keys()) - set(tweaks_defaults.keys())
                if no_default:
                    Logger.warning('Provided tweaks have no default: %s'%', '.join(no_default))

            d = tweaks_defaults.copy()  # shallow
            d.update(tweaks)
            tweaks = d

        elif tweaks:
            Logger.warning('%s given tweaks but %s does not set tweaks_defaults',
                           creature_id, self.__class__.__name__)

        self.tweaks = tweaks

        self.debug_visuals = debug_visuals

        self.orienting = False  # is currently orienting toward orienting_angle
        self.orienting_angle = 0
        self.orienting_throttle = 1.0

        # TODO just use a incrementing global for all creatures?
        self.phy_group_num = kwargs.get('phy_group_num', 1)

        self.environment_wref = None
        # mass and moment will be updated after subclass draws
        self.phy_body = body = phy.Body(1, 1)
        self.phy_body.velocity_limit = 1000  # TODO units?

        # Composite body parts that update every tick
        # Mapping part_name -> BodyPart
        self.__body_parts = {}

        # Set properties that will be used within draw()
        # pos and angle are stored in the physics objects
        body.position = kwargs.get('pos', (0, 0))
        body.angle = radians(kwargs.get('angle', 0.0))

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

        # TODO Need to rotate body parts about center as well

    @property
    def scale(self):
        return self._scale.x

    @scale.setter
    def scale(self, scale):
        # TODO what does z do for 2D?
        self._scale.xyz = (scale, scale, 1.0)

    def on_mass(self, o, mass):
        self.phy_body.mass = mass

    @property
    def body_parts(self):
        return self.__body_parts.values()

    def add_body_part(self, part):
        """Add a body part to this Creature and attach it the the physics space
        if the Creature is bound to an environment"""
        self.__body_parts[part.part_name] = part


        if self.environment_wref:  # Bound to environment
            env = self.environment_wref()
            if env is None:
                # environment was GC'd
                # This might happen if the old space was removed but this Creature object maintained
                # Don't know when we'd ever do this so warn for now
                Logger.warning('Creature environment_wref weakref is None, not binding body part to space')

            else:
                part.bind_physics_space(env.phy_space)


    def bind_environment(self, environment):
        """Attach to the given environment and its physics space.
        bind body_parts to physics space as well.

        Required environment attributes
        - phy_space -- cymunk Space
        """

        # Not planning on moving Creatures between environments
        assert self.environment_wref is None
        space = environment.phy_space

        # Cannot create weakref to space
        # Create a weakref to make sure avoid circular GC
        self.environment_wref = weakref_ref(environment)

        space.add(self.phy_body)  # add physical objects to simulated space
        if hasattr(self, 'phy_shape'):
            space.add(self.phy_shape)

        for bp in self.body_parts:
            bp.bind_physics_space(space)

    def unbind_environment(self):
        """Remove all of the Creature's physics objects from the physics space
        """
        env = self.environment_wref()
        if env is None:
            Logger.warning("%s.unbind_environment called but env weakref None", self.__class__.__name__)
            return

        space = env.phy_space

        for bp in self.body_parts:
            bp.unbind_physics_space(space)

        space.remove(self.phy_body)
        if hasattr(self, 'phy_shape'):
            space.remove(self.phy_shape)

    def destroy(self):
        """unbind from the environment and stop all clocks and other activities
        """
        self.unbind_environment()
        # (subclasses will override this to do more)

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
                x = dp(6)
                Triangle(points=(-x, -x, x, -x, 0, x))

                PopMatrix()

                # Orienting Line
                self._orienting_line_color = Color(rgba=(0.0, 1.0, 0.0, 0.8))
                self._orienting_line = Line(width=1.2)

            PopMatrix()
            PopState()

    def orient(self, angle, throttle=1.0):
        """Orient the Creature toward the angle, using body motion
        throttle 0.0 to 1.0 for how quickly to rotate
        """
        if angle is None:
            self.orienting = False
            if self.debug_visuals:
                self._orienting_line_color.a = 0.0
            return

        self.orienting = True
        self.orienting_angle = angle = fix_angle(angle)
        self.orienting_throttle = throttle
        self._half_orienting_angle_original_diff_abs = abs(angle-self.angle) / 2.0

        if self.debug_visuals:
            vec = Vec2d(50, 0).rotated_degrees(angle)
            self._orienting_line_color.a = 0.8
            self._orienting_line.points = (0, 0, vec.x, vec.y)

    def update(self, dt):
        """Called after physics space has done a step update"""

        # Optimization: Set angle and pos on phy_body directly to avoid extra function execution
        body = self.phy_body

        # 1. Apply forces to body
        # TODO drag, continuous force? how to update instead of adding new, just reset? look at arrows example

        drag_const = self.tweaks['drag_constant']  # drag coeficcent * density of fluid
        # TODO cos/sine of angle?
        drag_force = body.velocity.rotated_degrees(180) * (body.velocity.get_length_sqrd() * self.cross_area * drag_const)
        # TODO limit force here as in Gooey drag?
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

        env = self.environment_wref()
        if env is not None:
            out_of_bounds = False

            if y > env.height:
                y = 1
                out_of_bounds = True

            if y < 0:
                y = env.height - 1
                out_of_bounds = True

            if x > env.width:
                x = 1
                out_of_bounds = True

            if x < 0:
                x = env.width - 1
                out_of_bounds = True

            if out_of_bounds:
                # Trigger move of main body and body-parts
                self.pos = (x, y)
            else:
                self._translate.xy = (x, y)

        else:
            self._translate.xy = (x, y)

        # Needed at all?
        # update_creature()

    def adjust_part_tweak(self, part_name, tweak_name, value):
        if self.part_name == part_name:
            part = self
        else:
            part = self.__body_parts[part_name]

        if hasattr(part, 'adjust_tweak'):
            part.adjust_tweak(tweak_name, value)
        else:
            part.tweaks[tweak_name] = value

    # TODO this should be done differently, think about AOP/Component oriented programming
    def set_behavior(self, b):
        self.current_behavior = b
        # TODO think about this API
        b.attach(self)


class CreatureBodyPart(EventDispatcher):

    def __init__(self, creature=None, part_name=None, tweaks=None, **kwargs):
        super(CreatureBodyPart, self).__init__(**kwargs)

        if tweaks is None:
            tweaks = {}

        self.tweaks = tweaks

        # Set missing tweaks to default
        for tweak_name, value in self.tweaks_defaults.viewitems():
            if tweak_name not in tweaks:
                Logger.debug('%s missing tweak "%s" setting default value %s', self.__class__.__name__,
                             tweak_name, value)
                tweaks[tweak_name] = value

        self.creature = creature
        self.part_name = part_name

    def bind_physics_space(self, space):
        """Add all physics objects this body part created to the physics space
        """
        for o in self.phy_objects():
            space.add(o)

    def unbind_physics_space(self, space):
        for o in reversed(tuple(self.phy_objects())):
            space.remove(o)

    def translate(self, translation_vector):
        for body in self.phy_objects(body_only=True):
            body.position += translation_vector

        # Force visual update
        self.update()

    def adjust_tweak(self, name, value):
        self.tweaks[name] = value
