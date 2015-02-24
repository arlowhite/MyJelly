__author__ = 'awhite'

from kivy.graphics import Rectangle, Triangle, Color, Rotate, Translate, InstructionGroup, PushMatrix, PopMatrix, \
    PushState, PopState, Canvas, Mesh, Scale
from kivy.vector import Vector
from kivy.core.image import Image as CoreImage
from kivy.core.image import ImageLoader
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty
from kivy.graphics import StencilUse
from kivy.graphics.instructions import InstructionGroup

from kivy.clock import Clock

from drawn_visual import ControlPoint


# Don't think I want event dispatch, not needed for every creature and will be too much

# In Sacrifical Creatures I didn't want the overhead of Widgets, but in this game
# I'll try them out since it should make things easier and provide some practice

class Creature(Widget):
    "Something that moves every clock tick"

    def __init__(self, **kwargs):
        super(Creature, self).__init__(**kwargs)

        # self.pos = Vector(100, 100)

        self.angle = 0

        # FIXME Does velocity vector belong here?
        self.vel = Vector(0, 0)
        self.vel_y = 1

        self.draw()

        # on_X auto binds
        #self.bind(pos=self.update_pos)


    def draw(self):
        with self.canvas.before:
            PushMatrix()
            PushState()

        with self.canvas.after:
            PopMatrix()
            PopState()


        with self.canvas:
            Color(1, 1, 1, 1)

            self._trans = Translate()
            self._trans.xy = self.pos


            # self._rot = Rotate()
            # self._rot.angle = self.angle
            # mycanvas.add(self._rot)

            self.draw_creature()

    def on_pos(self, jelly_obj, coords):
        self._trans.xy = coords


    def set_angle(self, angle):
        self.angle = angle
        self._rot.angle = angle
        self.canvas.ask_update()

    def update(self, dt):
        # FIXME Better to always call update on all creatures, or schedule individually? Behavior control?
        # Velocity within Behavior code?
        # vel = Vector(0,0)
        self.pos += self.vel * dt
        self._trans.xy = self.pos
        #self._rot.angle += 1
        # best way to do this?
        #self._rot.angle %= 360

        self.update_creature()

        self.canvas.ask_update()

        #self.shape.pos = self.pos


    def set_behavior(self, b):
        self.current_behavior = b
        # TODO think about this API
        b.attach(self)


class Jelly(Creature):

    scale = NumericProperty(1.0)

    def __init__(self, **kwargs):

        self.texture = None
        self._flip_texture_vertical = False

        super(Jelly, self).__init__(**kwargs)


        # The texture coordinate dimensions I choose could be anything if I just Scale() instead of
        # recalculating them for size changes, so I'll just use the Image.size

        w = self.texture_img.width
        h = self.texture_img.height


        # Initial simple vertices
        vertices = []
        # u,v pos are 0 to 1.0
        vertices.extend((w / 2, h / 2, 0.5, 0.5))
        vertices.extend((0, 0, 0, 0))
        vertices.extend((0, h, 0, 1))
        vertices.extend((w, h, 1, 1))
        vertices.extend((w, 0, 1, 0))

        # tex_coords [u, v, u + w, v, u + w, y + h, u, y + h]
        # No effect: tex_coords=(0.0, 0.0, 1.0, 0.0, 1.0, -1.0, 0.0, -1.0)

        # mode: Can be one of points, line_strip, line_loop, lines, triangles, triangle_strip or triangle_fan.

        self.update_mesh_vertices(vertices)
        self.on_scale(self, self.scale)


        #self.bind(size=self.on_size)


        #self.texture_img = CoreImage('media/images/jelly.png')

        #self.texture_img.texture.flip_vertical()



    #def draw_creature_before(self):


#        print(im.texture.tex_coords)



        #self.texture_img.texture.tex_coords = (0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0)
        #uvpos 0.0, 1.0
        #uvsize 10., -1.0
        #tex_coords (0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0)

    def load_image(self):
        # self.texture_img = CoreImage('media/images/jelly.png')
        #self.texture_img = texture_img

        im = ImageLoader.load('media/images/jelly.png')
        # Texture is and should be flipped, however, Mesh does not use Texture.tex_coords
        # Created bug on GitHub/kivy

        # Prevent tex_coords flip
        #im._data[0].flip_vertical = False
        self.texture_img = im
        texture = im.texture
        self.texture = texture
        # flip_vertical=True  (0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0)
        # flip_vertical=False (0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0)
        if texture.tex_coords==(0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0):
            # Image tex_coords was flipped vertically
            # Could flip in texture itself and set tex_coords to normal, but it's a bit harder
            self._flip_texture_vertical = True

    def draw_creature(self):
        self.load_image()

        # Control size without recalculating vertices
        self._mesh_scale = Scale(1, 1, 1)

        self.mesh = Mesh(mode='triangle_fan', texture=self.texture)


    def update_mesh_vertices(self, vertices):
        "Create/Recreate mesh, indices loops around to 2nd vertex for you"

        # TODO u,v coords don't seem to be affected by Scale when changed, need to invert coords
        if self._flip_texture_vertical:
            for i in range(0, len(vertices), 4):
                # v coord
                v = vertices[i+3]
                vertices[i+3] = 1-v

        indices = range(len(vertices)/4)
        indices.append(1)

        self.mesh.vertices = vertices
        self.mesh.indices = indices

    def update_creature(self):
        # self.vertices[5] += 1
        #verts = list(self.vertices)
        # verts = self.mesh.vertices
        # verts[8] += 1
        # verts[9] += 1
        # self.mesh.vertices = verts

        # Tests
        #self.x += 1
        #self.size = (self.width-1, self.height-1)
        #self.scale*=1.1

        if self.y > self.parent.height:
            self.y = 0

        if self.x > self.parent.width:
            self.x = 0


    def on_size(self, widget, new_size):
        if hasattr(self, '_mesh_scale'):
            # Scale the Mesh relative to the Image size vertices were created with
            self._mesh_scale.xyz = (new_size[0] / self.texture_img.width, new_size[1] / self.texture_img.height, 1)

        if hasattr(self, '_mesh_trans'):
            # flip_vertical correction needs to update Translate when height changes
            self._mesh_trans.y = new_size[1]

    def on_scale(self, widget, new_scale):
        self.size = (self.texture_img.width * self.scale, self.texture_img.height * self.scale)
