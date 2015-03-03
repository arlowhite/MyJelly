__author__ = 'awhite'

import types


def evaluate_thing(thing):
    "Evaluate thing, if number return, if func return call, if generator next"
    if isinstance(thing, types.IntType) or isinstance(thing, types.FloatType):
        return thing
    elif isinstance(thing, types.FunctionType):
        return thing()
    elif isinstance(thing, types.GeneratorType):
        return next(thing)

    raise ValueError('Unknown thing: '+str(type(thing))+str(thing))
