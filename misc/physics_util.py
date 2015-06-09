__author__ = 'awhite'

# from math import radians
from cymunk import Vec2d

def cleanup_space(space):
    """Remove all constraints, shapes, and bodies from a Cymunk Space
    Note: Set your space attribute to None to force earlier garbage collection
    """
    if space is None:
        return

    space.remove(*space.constraints)
    assert len(space.constraints) == 0

    # shapes is a dict for some reason
    shapes = space.shapes.values()
    space.remove(*shapes)
    assert len(space.shapes) == 0

    space.remove(*space.bodies)
    assert len(space.bodies) == 0

# TODO maybe contribute these to cymunk
def world_pos_of_offset(body, offset_pos):
    """Calculates the world vector to the offset_pos relative to the body.

    :param body: the cymunk body
    :type body: phy.Body
    :param offset_pos: position of the offset relative to body (as if angle=0)
    :type offset_pos: tuple or Vec2d (any object where pos[0], pos[1] denotes x, y)

    :returns offset_world_pos
    :rtype : Vec2d
    """

    # Rotate the vector to align with body angle
    offset_world_vec = Vec2d(offset_pos[0], offset_pos[1])
    # calling radians myself avoids function call in Vec2d (unless Cython optimizes somehow)
    offset_world_vec.rotate(body.angle)
    offset_world_vec += body.position
    return offset_world_vec


def offset_to_pos(body, pos):
    """Calculates the anchor offset (as used in constraints) for the given world position
    relative to the given body.

    :param body: the cymunk body
    :type body: phy.Body
    :param pos: position in world coordinates to calculate an offset to.
    :type _pos: tuple or Vec2d (any object where pos[0], pos[1] denotes x, y)

    :returns offset vector relative to body
    :rtype Vec2d
    """

    pos_vec = Vec2d(pos[0], pos[1])
    pos_vec -= body.position
    pos_vec.rotate(-body.angle)
    return pos_vec
