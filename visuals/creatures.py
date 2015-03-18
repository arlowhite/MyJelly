__author__ = 'awhite'

import random
from math import cos, sin, radians

from kivy.logger import Logger
from kivy.graphics import Rectangle, Triangle, Color, Rotate, Translate, InstructionGroup, PushMatrix, PopMatrix, \
    PushState, PopState, Canvas, Mesh, Scale
from kivy.vector import Vector
from kivy.core.image import Image as CoreImage
from kivy.core.image import ImageLoader
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import StencilUse
from kivy.graphics.instructions import InstructionGroup
from kivy.clock import Clock

from drawn_visual import ControlPoint
from animations import MeshAnimator, setup_step


# Don't think I want event dispatch, not needed for every creature and will be too much

# In Sacrifical Creatures I didn't want the overhead of Widgets, but in this game
# I'll try them out since it should make things easier and provide some practice

# TODO Probably just do EventDispatcher instead of Widget? Performance test # of Jellies limit
# Single animation update loop instead of Animation Clocks for each? or chain Animations? &=
class Creature(Widget):
    "Something that moves every clock tick"

    scale = NumericProperty(1.0)

    # angle in degrees
    # 0 points up, positive is counter-clockwise
    angle = NumericProperty(0.0)

    speed = NumericProperty(0.0)

    def __init__(self, **kwargs):
        self.angle_radians = 0
        super(Creature, self).__init__(**kwargs)

        # self.pos = Vector(100, 100)

        # FIXME Does velocity vector belong here?
        self.vel = Vector(0, 0)
        self.vel_y = 1

        self.draw()

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

            self._trans = Translate()
            self._trans.xy = self.pos

            self._rot = Rotate()
            self._rot.angle = self.angle

            self.draw_creature()

    def on_pos(self, jelly_obj, coords):
        self._trans.xy = coords

    def on_scale(self, _, scale):
        # TODO what does z do for 2D?
        self._scale.xyz = (scale, scale, 1.0)

    def on_angle(self, _, angle):
        self.angle_radians = radians(angle)
        self._rot.angle = angle
        # FIXME angle%360? or -180 to 180  see what Scale does
        self.canvas.ask_update()  # TODO update necessary?

    def update(self, dt):
        # Want to avoid creating many Vector objects?
        # Vector operations creating new: rotate(), *
        # Modify self: *=

        # Possibilities
        # pos_vec += velocity_vec * dt  (velocity_vec angle

        # Rotate vector by angle each time
        # No Vector() creation
        # velocity_vec[0] = 0
        # velocity_vec[1] = speed*dt
        # TODO Vector rotates same way?
        # pos_vec += velocity_vec.rotate(angle, self=True)  # would need to modify rotate

        # Vectors involve object creation and function calls. Just do the math myself

        move = self.speed * dt  # How many pixels to move along velocity vector
        #  +counter-clockwise (axis vertical)

        x = self.x - sin(self.angle_radians)
        y = self.y + cos(self.angle_radians)

        parent = self.parent
        if y > parent.height:
            y = 1

        if y < 0:
            y = parent.height - 1

        if x > parent.width:
            x = 1

        if x < 0:
            x = parent.width - 1

        self.pos = (x, y)

        # Needed at all?
        # update_creature()

        # self.canvas.ask_update()

        #self.shape.pos = self.pos


    def set_behavior(self, b):
        self.current_behavior = b
        # TODO think about this API
        b.attach(self)


class Jelly(Creature):

    def __init__(self, **kwargs):

        self._bell_animator = None

        # Ideally Animation would be more abstract
        # However, this game focuses only on Jellies
        # So it's much easier to hard-code the knowledge of bell pulses, tentacle drift, etc.
        self.store = kwargs.get('jelly_store')

        super(Jelly, self).__init__(**kwargs)

    def draw_creature(self):
        # called with canvas
        store = self.store
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
        Logger.debug('Jelly: centering adjustment %s', adjustment)
        # Translate(xy=adjustment)
        t = Translate()
        t.xy = adjustment

        img = CoreImage(anim['image_filepath'])
        mesh = Mesh(mode=mesh_mode, texture=img.texture)
        a = MeshAnimator.from_animation_data(anim)
        a.mesh = mesh
        a.start_animation()
        self._bell_animator = a

        PopMatrix()

        # Visualize pos point
        Color(rgba=(1, 0, 0, 0.6))
        x = 6
        Triangle(points=(-x, -x, x, -x, 0, x))

    # TODO thing about what is controled in MeshAnimation vs Creature
    def bell_pulse_complete(self, anim_seq, widget):
        Clock.schedule_once(self.animate_bell, random.triangular(0.3, 2.0, 0.5))

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
