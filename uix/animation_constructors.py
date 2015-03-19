from kivy import Logger
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.graphics.context_instructions import Color
from kivy.graphics.vertex_instructions import Rectangle, Mesh
from kivy.properties import ListProperty, BoundedNumericProperty, BooleanProperty, StringProperty
from kivy.uix.scatter import Scatter
from kivy.vector import Vector
from visuals.animations import MeshAnimator, setup_step
from visuals.drawn_visual import ControlPoint

__author__ = 'awhite'


class AnimationConstructor(Scatter):
    """Visual animation constructor.
    Shows a single Mesh texture in the center.
    Allows manipulation of ControlPoints within its size.

    """

    control_points = ListProperty([])
    animation_step = StringProperty(setup_step)
    # Image can be moved and zoomed by user to allow more precise ControlPoint placement.
    move_resize = BooleanProperty(False)
    animating = BooleanProperty(False)  # animating controlpoints
    animate_changes = BooleanProperty(True)

    control_points_disabled = BooleanProperty(False)
    control_points_opacity = BoundedNumericProperty(1.0, min=0.0, max=1.0)
    image_opacity = BoundedNumericProperty(1.0, min=0.0, max=1.0)

    def __init__(self, **kwargs):
        self.autosize = True
        self.mesh_mode = 'triangle_fan'
        self.setup_step = setup_step
        self.mesh_attached = False
        self._image_size_set = False
        self.mesh = None
        # FIXME test state restore from different animation_step, trigger on_animation, check mesh_attched on CPs
        self.animation_step = setup_step
        self.steps = kwargs.get('steps', [self.animation_step]) # all steps
        self._previous_step = self.animation_step
        self.faded_image_opacity = 0.5
        self._moved_control_point_trigger = Clock.create_trigger(self.on_control_point_moved)
        self._control_point_opacity_trigger = Clock.create_trigger(self._animate_control_point_opacity)

        super(AnimationConstructor, self).__init__(**kwargs)

        self.bind(move_resize=self.decide_disable_control_points, animating=self.decide_disable_control_points)

        with self.canvas:
            self.image_color = Color(rgba=(1, 1, 1, 1))
            self.image = Rectangle()

            self.mesh_color = Color(rgba=(1, 1, 1, 1))
            self.mesh = Mesh(mode=self.mesh_mode)


    def set_animation_data(self, data, animation_step=setup_step):
        """Resets AnimationConstructor, displays image centered"""
        # data is a dictionary of image_filepath, vertices[], indices[]
        # TODO code that creates MeshAnimator from this should be refactored
        # This should update jelly_store; other code should read it and create the MeshAnimation

        # TODO Work on reseting state? Just create new instead?

        Logger.debug('animation_data set')
        self.animate_changes = False
        try:
            # self has default size at this point, sizing must be done in on_size

            with self.canvas:
                # mipmap=True changes tex_coords and screws up calculations
                # TODO Research mipmap more
                cimage = CoreImage(data['image_filepath'], mipmap=False)


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


            self.mesh_mode = data.get('mesh_mode', self.mesh_mode)
            triangle_fan_mode = self.mesh_mode == 'triangle_fan'

            self.animation_steps_order = data.get('steps_order', self.animation_steps_order)

            # indices are actually recalculated, nowhere to set them
            try:
                steps = data['steps']
            except KeyError:
                # No steps defined, nothing to do
                return

            mesh = self.mesh

            # Process step zero, create ControlPoints
            step_zero = steps[setup_step]
            verts = step_zero['vertices']
            cps = []
            num_verts = len(verts)
            if num_verts == 0:
                # Nothing else to do, everything below creates ControlPoints
                return

            # Not a fan of how much internal knowledge this code requires, but not worth refactoring too much now
            # First-pass on setup_step
            for x in range(1 if triangle_fan_mode else 0, num_verts/4):
                # x,y pos
                cp = ControlPoint(moved_point_trigger=self._moved_control_point_trigger)
                cp.vertex_index = x
                # Adjust index to position in vertices list
                cp.positions[setup_step] = (verts[x*4], verts[x*4+1])
                cps.append(cp)

            # Note: items() in Py3
            for step, step_data in steps.viewitems():
                if step == setup_step:
                    continue

                self.steps.append(step)
                verts = step_data['vertices']
                if len(verts) != num_verts:
                    raise ValueError('steps vertices different lengths!')

                # Update ControlPoint.positions with this position/step
                for cp in cps:
                    index = cp.vertex_index
                    cp.positions[step] = (verts[index*4], verts[index*4+1])

            for cp in cps:
                # cp.move_to_position_index(self.animation_step, animate=False)
                cp.mesh = mesh  # set after so on_pos doesn't do anything
                self.add_widget(cp)
                # cp.update_trail_line()  # cp.on_pos calls this

            self.control_points = cps

            self._previous_step = setup_step  # on_animation_step will reset mesh

            # Setting animation_step will move the ControlPoints for us and figure out mesh attachment
            need_dispatch = self.animation_step == animation_step  # will need to dispatch if step doesn't change
            self.animation_step = animation_step
            if need_dispatch:
                self.property('animation_step').dispatch(self)

        finally:
            self.animate_changes = True

    def get_animation_data(self):
        "Generate animation data for storage in store"

        # animation_data vs control_point data
        # first vertex is the triangle_fan point....
        # just make that a visible unmoveable point?

        # image_filepath (already set)
        # indices[]
        # steps:{STEP:{vertices:[]}

        data = {}
        steps = {}

        data['mesh_mode'] = self.mesh_mode
        data['steps_order'] = self.animation_steps_order

        # Make sure all required steps are available, even if we this hasn't shown them yet.
        step_set = set(self.animation_steps_order)
        if setup_step not in step_set:
            step_set.add(setup_step)


        for step in step_set:
            verts, indices = self.calc_mesh_vertices(step, update_mesh=False)
            # indices always recalculated at the moment, but save for possible future use
            if 'indices' not in data:
                data['indices'] = indices

            step_data = {}
            step_data['vertices'] = verts
            # FIXME hardcoded 2.4s to open, 0.65 to close
            # duration to reach this step
            step_data['duration'] = 2.4 if step=='open_bell' else 0.65

            steps[step] = step_data

        data['steps'] = steps
        return data


    def on_parent(self, _, parent):
        parent.bind(size=self.on_parent_size)

    def on_parent_size(self, widget, size):
        if not self.autosize:
            # Other code will set pos/scale
            return

        Logger.debug(self.__class__.__name__ + '.on_parent_size %s', size)
        p_width, p_height = size

        # Ignore default/zero sizes
        if p_height == 0.0 or p_height == 1:
            Logger.debug('ignoring size %s', size)
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
        Logger.debug(self.__class__.__name__ + '.on_size %s', size)
        self.bbox_diagonal = (size[0]**2 + size[1]**2)**0.5


    def on_image_opacity(self, _, opacity):
        if self.animate_changes:
            Animation(a=opacity).start(self.image_color)
        else:
            self.image_color.a = opacity

    def on_control_points(self, widget, points):
        # If on first animation step, Update mesh to preview Mesh cut
        if self.animation_step == setup_step and len(points) >= 3:
            self.calc_mesh_vertices(step=setup_step)

            # Fade image a bit
            #if self.image.opacity > self.faded_image_opacity:
                #Animation(opacity=self.faded_image_opacity).start(self.image)

            self.image_opacity = self.faded_image_opacity

    def on_control_point_moved(self, _):
        # one or more ControlPoints moved
        self.calc_mesh_vertices(preserve_uv=self.animation_step!=setup_step)

    def on_animation_step(self, widget, step):
        """animation_step changed.
        move control points to step with animation
        Set mesh_attached=False if on setup_step
        """
        Logger.debug('on_animation_step %s', step)
        if not isinstance(step, basestring):
            raise ValueError('animation_step must be a string, given %s'%step, type(step))

        # Track all possible step keys
        if step not in self.steps:
            self.steps.append(step)

        resume_animation = self.animating
        if self.animating:
            # Switched step while previewing animation
            self.preview_animation(False)

        if step == setup_step:
            self.image_opacity = self.faded_image_opacity

            # ControlPoints will detach mesh after animation in: move_control_points()
            self.mesh_attached = False

        else:
            # Not first animation step
            self.image_opacity = 0.0

            mesh = self.mesh

            if self._previous_step == setup_step:
                # Redo base vertices when moving from 0 to other
                Logger.debug('Recalculating vertices/indices during transition from step 0')
                self.calc_mesh_vertices(step=setup_step, preserve_uv=False)

            if not self.mesh_attached:
                # attach before moving to other animation steps
                for cp in self.control_points:
                    cp.attach_mesh(True)

                self.mesh_attached = True

        self.move_control_points(step, detach_mesh_after=step == setup_step)

        self._previous_step = step

        if resume_animation:
            self.preview_animation()

    def calc_mesh_vertices(self, step = None, update_mesh=True, preserve_uv=True):
        """Calculate Mesh.vertices and indices from the ControlPoints
        If step omitted, uses ControlPoints at current position, otherwise
        vertices at that animation step (ControlPoint.positions[step]).
        Central vertice at center is added as first item in list if mesh_mode=='triangle_fan'
        preserve_uv: Do not overwrite the uv coordinates in the current Mesh.vertices
        (only has an effect if update_mesh==True and vertices are already set)

        returns vertices, indices
        """
        if step is not None and not isinstance(step, basestring):
            raise ValueError('step must be a string')

        num = len(self.control_points)
        if num == 0:
            Logger.warning("AnimationConstructor: Called calc_mesh_vertices without any control_points")
            return [], []


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


        if triangle_fan_mode and step==setup_step:
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
        # enumerate always goes through all items, start is just where the count starts
        for index, cp in enumerate(self.control_points, start=start):
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
            mesh_verts = self.mesh.vertices
            num_mesh_verts = len(mesh_verts)

            if preserve_uv and num_mesh_verts > 0:
                assert num_mesh_verts == len(verts)

                # Only overwrite x, y mesh coords
                for x in range(0, num_mesh_verts, 4):
                    mesh_verts[x] = verts[x]
                    mesh_verts[x+1] = verts[x+1]

                self.mesh.vertices = mesh_verts

            else:
                self.mesh.vertices = verts

            self.mesh.indices = indices

        return verts, indices

    def move_control_points(self, position_index, detach_mesh_after):
        "Move all of the Control Points to the specified position index"
        for cp in self.control_points:
            cp.move_to_position_index(position_index, detach_mesh_after=detach_mesh_after, animate=self.animate_changes)


    def preview_animation(self, activate_preview=True):
        "Start/Stop animation preview"

        if activate_preview:
            a = MeshAnimator.from_animation_data(self.get_animation_data())
            a.mesh = self.mesh
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
        self._control_point_opacity_trigger()

    def _animate_control_point_opacity(self, _):
        # Called through trigger to avoid starting an Animation and then canceling it immediately
        if hasattr(self, '_control_point_opacity_animation'):
            for cp in self.control_points:
                self._control_point_opacity_animation.cancel(cp)

            self._control_point_opacity_animation = None

        opacity = self.control_points_opacity
        if self.animate_changes:
            a = Animation(duration=0.5, opacity=opacity)
            for cp in self.control_points:
                a.start(cp)
            self._control_point_opacity_animation = a
        else:
            for cp in self.control_points:
                cp.opacity=opacity

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

            if self.animation_step != setup_step:
                # Only create ControlPoints in first step
                return False

            # None were close enough, create a new ControlPoint
            ctrl_pt = ControlPoint(moved_point_trigger=self._moved_control_point_trigger)
            ctrl_pt.mesh = self.mesh
            ctrl_pt.position_index = self.animation_step

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