__author__ = 'awhite'

import random

from kivy.logger import Logger
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import BoundedNumericProperty, BooleanProperty, ListProperty
from kivy.clock import Clock

import cymunk as phy

from misc.util import cleanup_space

class BasicEnvironment(RelativeLayout):
    """Simple environment"""

    # TODO different update intervals for physics/animations?
    update_interval = BoundedNumericProperty(1 / 60.0, min=1 / 120.0, max=1.0)
    initialized = BooleanProperty(False)
    paused = BooleanProperty(False)
    creatures = ListProperty()

    # TODO maybe add_creature, remove_creature events

    def on_size(self, _, size):
        if size == [1, 1]:
            return

        self.initialize()
        # Only initialize once
        self.unbind(size=self.on_size)

    def on_paused(self, _, paused):
        # If paused is False when initializing, this method will be called
        if paused:
            Clock.unschedule(self.update_simulation)
        else:
            Clock.schedule_interval(self.update_simulation, self.update_interval)

    def add_creature(self, creature):
        Logger.debug('%s: add_creature %s', self.__class__.__name__, creature.creature_id)
        self.canvas.add(creature.canvas)  # TODO is this right?
        self.creatures.append(creature)
        if self.initialized:
            creature.bind_environment(self)

    def remove_creature(self, creature):
        self.creatures.remove(creature)
        self.canvas.remove(creature.canvas)
        creature.destroy()

    def destroy(self):
        Logger.debug('{}: on_leave() unscheduling update_simulation and cleaning-up physics space'
                     .format(self.__class__.__name__))

        self.paused = True

        # Clean-up physics space
        cleanup_space(self.phy_space)

        # This seems to force garbage collection immediately
        self.phy_space = None

    def update_simulation(self, dt):
        # Could pass dt, but docs state:
        # Update the space for the given time step. Using a fixed time step is
        # highly recommended. Doing so will increase the efficiency of the contact
        # persistence, requiring an order of magnitude fewer iterations to resolve
        # the collisions in the usual case.
        self.phy_space.step(self.update_interval)

        for c in self.creatures:
            c.update(dt)

    def initialize(self):
        "called after size set once"
        Logger.debug('%s: initialize()', self.__class__.__name__)

        # Setup physics space
        # TODO need to respond to resizes?
        # http://niko.in.ua/blog/using-physics-with-kivy/
        # kw - is some key-word arguments for configuting Space
        self.phy_space = space = phy.Space()
        # space.damping = 0.9

        # wall = phy.Segment(phy.Body(), (0, 1), (3000, 1), 0.0)
        # wall.friction = 0.8
        # space.add(wall)
        #
        # wall = phy.Segment(phy.Body(), (1, 3000), (1, 3000), 0.0)
        # wall.friction = 0.8
        # space.add(wall)

        # Clock.schedule_interval(self.change_behavior, 20)
        # self.change_behavior(0.0)

        if self.creatures:
            # Creatures were added before initilization and need to be bound to environment
            for creature in self.creatures:
                creature.bind_environment(self)

        self.initialized = True
        if not self.paused:
            #
            self.on_paused(self, False)

    def change_behavior(self, dt):
        # TODO refactor behavior code
        for c in self.creatures:
            angle = c.angle + random.randint(-180, 180)
            print('change_behavior: current angle=%f  orienting %f deg' % (c.angle, angle))
            c.orient(angle)
