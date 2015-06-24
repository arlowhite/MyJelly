__author__ = 'awhite'

from functools import wraps

import types
import warnings


def evaluate_thing(thing):
    "Evaluate thing, if number return, if func return call, if generator next"
    if isinstance(thing, types.IntType) or isinstance(thing, types.FloatType):
        return thing
    elif isinstance(thing, types.FunctionType):
        return thing()
    elif isinstance(thing, types.GeneratorType):
        return next(thing)

    raise ValueError('Unknown thing: '+str(type(thing))+str(thing))


def not_none_keywords(*not_none_args):
    """Checks that the specified keyword arguments are not None"""
    def check_not_none(f):
        # Verify variable names are actually keyword arguments
        missing = [name for name in not_none_args if name not in f.func_code.co_varnames]
        if missing:
            raise AssertionError('{} has no keyword argument named: {}'
                                 .format(f.func_name, ', '.join(missing)))

        @wraps(f)
        def not_none_keywords_wrapper(*args, **kwargs):
            for var_name in not_none_args:
                try:
                    if kwargs[var_name] is None:
                        raise AssertionError('Required keyword argument "{}" is None!'.format(var_name))

                except KeyError:
                    raise AssertionError('Required keyword not specified: {}'.format(var_name))

            return f(*args, **kwargs)

        # new_f.func_name = f.func_name
        # co_name
        return not_none_keywords_wrapper

    return check_not_none

