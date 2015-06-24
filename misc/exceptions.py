__author__ = 'awhite'

# Custom Exceptions


class InsufficientData(Exception):
    """Not enough data is associated with the game object to render it.
    Constructable objects should raise this exception to indicate missing data
    and reserve ValueError and other exceptions for bad data.
    """
