__author__ = 'awhite'

from collections import namedtuple

from kivy.clock import Clock
from kivy.animation import Animation
from kivy.event import EventDispatcher
from kivy.properties import NumericProperty, ObjectProperty

from misc.util import evaluate_thing

# RelativeLayout or Scatter seems overcomplicated and causes issues
# just do it myself, don't really need to add_widget()
# TODO Padding so can pickup ControlPoint on edge

# animation step name for the step defining u, v
setup_step='__setup__'

VerticesState = namedtuple('VerticesState', 'vertices, duration, delay, horizontal_transition, vertical_transition')

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

    mesh = ObjectProperty(None)

    def __init__(self, **kwargs):
        self.vertices_states = []
        self.previous_step = 0
        self._animation = None
        self.initial_vertices = None
        self.initial_indices = None

        super(MeshAnimator, self).__init__(**kwargs)


    def add_vertices(self, vertices, duration=1.0, delay=None,
                     horizontal_transition='linear', vertical_transition='linear', uv_change=False):
        """Add a set of vertices.
        duration: Seconds taken to reach vertices at this step.
        delay: Seconds to delay before beginning next animation after this step.
        horizontal|vertical_transition: transition to use when transferring to vertices at this step.

        duration & delay can be number, function, or generator
        TODO Implement uv_change if needed, currently u, v coordinates are never updated from the first step.
        """
        num = len(self.vertices_states)
        if num > 0 and len(self.vertices_states[0].vertices) != len(vertices):
            raise ValueError('Mismatched number of vertices: %d vs %d'%(num, len(vertices)))

        self.vertices_states.append(VerticesState(vertices, duration, delay, horizontal_transition, vertical_transition) )


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
        self._previous_step_vertices = self.vertices_states[prev].vertices
        self.step = step
        self._next_step_vertices = self.vertices_states[step].vertices

        state = self.vertices_states[self.step]
        dur = evaluate_thing(state.duration)

        # Setting properties will set vertices to previous_step
        self.horizontal_fraction = 0.0
        self.vertical_fraction = 0.0

        # Go from 0 to 1 each time, try saving Animation
        # PERF try keeping Animation instance, need to change transition/duration each time
        a = Animation(horizontal_fraction=1.0, transition=state.horizontal_transition, duration=dur)
        a &= Animation(vertical_fraction=1.0, transition=state.vertical_transition, duration=dur)
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
        delay_thing = self.vertices_states[self.step].delay
        if delay_thing:
            Clock.schedule_once(self.start_animation, evaluate_thing(delay_thing))

        else:
            self.start_animation()


    # def on_horizontal_fraction(self, *args):
    #     print('on_horizontal_fraction', args)

    # Note: This method is performance sensitive!
    def on_vertical_fraction(self, widget, vert):

        # Do all work in one event function for efficency (horizontal should have been updated before this because of creation order.
        # TODO: Measure performance. Numpy math? Kivy Matrix math?

        horiz = self.horizontal_fraction

        in_verts = self._previous_step_vertices
        out_verts = self._next_step_vertices

        mesh = self.mesh
        verts = mesh.vertices
        # Skip central point, Go through by 4's
        # Vertex lists conform to Mesh.vertices
        # Perf: NumyPy able to calculate faster?
        for x in range(0, len(in_verts), 4):
            x_coord = (out_verts[x]-in_verts[x]) * horiz + in_verts[x]
            y = x+1
            y_coord = (out_verts[y]-in_verts[y]) * vert + in_verts[y]

            verts[x] = x_coord
            verts[y] = y_coord

        mesh.vertices = verts

    def on_mesh(self, _, mesh):
        mesh.vertices = self.initial_vertices
        mesh.indices = self.initial_indices

    @staticmethod
    def from_animation_data(data):
        """Construct a MeshAnimator from animation_data.
        Tip: Remember to set mesh"""
        a = MeshAnimator()



        # FIXME get these from animation_data
        bell_horiz_transition_out = 'in_back'
        bell_vert_transition_out = 'out_cubic'
        bell_horiz_transition_in = 'in_sine'
        bell_vert_transition_in = 'out_back'
        # TODO delay random.triangular(0.3, 2.0, 0.5)

        steps = data['steps']
        a.initial_vertices = steps[setup_step]['vertices']
        a.initial_indices = data['indices']

        # u, v coordinates from setup
        for step in data['steps_order']:
            verts = steps[step]['vertices']
            a.add_vertices(verts, duration=0.5, horizontal_transition='in_back', vertical_transition='out_cubic')

        return a


# Issues:
# Idea: Currently, ControlPoints scale with Scatter, could reverse/reduce this with an opposite Scale maybe.
# ScatterPlane works by changing collide_point,



