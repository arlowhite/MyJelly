__author__ = 'awhite'

# Singletonish module that keeps kivy stores open for reading/writing state.

import os.path as P
import os
import inspect
import uuid

from kivy.storage.jsonstore import JsonStore
from kivy.app import App
from kivy.logger import Logger
from datetime import datetime

import constructable

# Mapping of class paths to classes allowed to be constructed from JSON
constructable_members = {}
for member in inspect.getmembers(constructable):
    if member[0].startswith('_'):
        continue

    clazz = member[1]
    path = '{}.{}'.format(clazz.__module__, clazz.__name__)
    constructable_members[path] = clazz

from misc.exceptions import InsufficientData

jelly_stores = {}
app_store = None

class LazyJsonStore(JsonStore):
    # Does not sync right away
    # puts merge by default

    def store_put(self, key, value):
        if key in self._data:
            # Merge dictionaries instead of replacing
            self._data[key].update(value)

        else:
            self._data[key] = value

        self._is_changed = True
        return True

    # Don't store_sync every time
    def put(self, key, **values):
        return self.store_put(key, values)

    def delete(self, key):
        return self.store_delete(key)


def get_user_data_dir():
    app = App.get_running_app()
    return app.user_data_dir

def get_jellies_dir():
    data_dir = get_user_data_dir()
    jellies = P.join(data_dir, 'jellies')
    if not P.exists(jellies):
        os.mkdir(jellies)

    return jellies

def load_app_storage():
    global app_store
    if app_store is None:
        Logger.debug('state_storage: Opening app.json')
        app_store = LazyJsonStore(P.join(get_user_data_dir(), 'app.json'))

    return app_store


def __jelly_json_path(jelly_id):
    return P.join(get_jellies_dir(), jelly_id+'.json')

# This should probably be somewhere else (maybe jelly.py?),
# but this is as good a spot as any for now.
def new_jelly(image_filepath):
    "Creates a new jelly store and id and returns the id"

    # TODO If image used before, ask if want to open that Jelly
    # TODO Copy image file for safe keeping?
    # TODO check if image file
    jelly_id = uuid.uuid4().hex
    jelly = load_jelly_storage(jelly_id)
    jelly.put('info', image_filepath=image_filepath)

    # TODO This defines the parts available in the menu
    # In the future user might change this list through the GUI to define optional parts
    jelly['info']['creature_constructors'].extend(('jelly_bell', 'tentacles'))

    jelly.store_sync()  # As soon as image is saved, save jelly state
    return jelly_id

def load_jelly_storage(jelly_id):
    if jelly_id is None or len(jelly_id) < 1:
        raise ValueError('Invalid jelly_id: %s', jelly_id)

    global jelly_stores
    if jelly_id not in jelly_stores:
        path = __jelly_json_path(jelly_id)

        new_store = not P.exists(path)

        if new_store:
            Logger.debug('state_storage: Creating new store %s', path)
        else:
            Logger.debug('state_storage: Opening %s', path)

        try:
            store = LazyJsonStore(path)
        except ValueError:
            # FIXME This is bad, should capture bad file for release
            Logger.error('Failed to load JsonStore from file %s', path)
            #os.remove(path)
            raise

        if new_store:
            store['info'] = {'created_datetime': datetime.utcnow().isoformat(),
                             'id': jelly_id,
                             'creature_constructors': []}

        jelly_stores[jelly_id] = store


    return jelly_stores[jelly_id]

def load_all_jellies():
    jellies_dir = get_jellies_dir()
    # TODO sort jellies? last access?
    jellies = []
    for filename in os.listdir(jellies_dir):
        jelly_id, ext = P.splitext(filename)

        if ext == '.json':
            try:
                jellies.append(load_jelly_storage(jelly_id))
            except ValueError:
                Logger.error('Failed to load %s, will not be in all_jellies list', jelly_id)
                pass
        else:
            Logger.warning('state_storage: Non json file in jellies "%s"', filename)

    return jellies

def delete_jelly(jelly_id):
    if jelly_id in jelly_stores:
        del jelly_stores[jelly_id]

    path = __jelly_json_path(jelly_id)
    if P.exists(path):
        Logger.info("Removing Jelly %s JSON: %s", jelly_id, path)
        os.remove(path)


valid_construct_value_types = frozenset((str, unicode, int, long, float, bool, list))

def lookup_constructable(store_node):
    """Lookup the Constructor class for a store node.
     Example: {'visuals.creatures.jelly.JellyBell': {'kwarg1': 'foo}}

     Returns (Constructor, constructor_path, arguments_dict)

     Raises AssertionError if unexpected data.
     Raises KeyError if not a valid Constructor to access.
    """

    if not isinstance(store_node, dict):
        raise AssertionError('Expected store_node to be a dict')

    if len(store_node) != 1:
        raise AssertionError('Expect just one key that is a Constructor module path, given {}'.format(object.keys()))

    constructor_path, arguments_dict = store_node.items()[0]
    Constructor = constructable_members[constructor_path]
    return Constructor, constructor_path, arguments_dict

# keys in creature storage that are actually a dictionary
__actual_dictionaries = ('tweaks')

def construct_value(store_node, **merge_kwargs):
    """Construct a value from a JSON object retrieved from storage.
    dicts will be recursively constructed. The root dict should have just on key & value.

    merge_kwargs -- optional additional kwargs to merge into kwargs of Constructor

    For example:
    {'visuals.creatures.jelly.JellyBell':{
    mesh_animator:X,
    mesh_mode:X
    }

    Where value of X is passed to recursive call of construct_value. Then JellBell() constructor
    is called.

    Non-dicts are returned if they are valid types.
    """

    if isinstance(store_node, dict):
        Constructor, constructor_path, arguments_dict = lookup_constructable(store_node)

        kwargs = {}
        for argument_name, value in arguments_dict.viewitems():
            # Terrible hack, but simplest
            if isinstance(value, dict) and argument_name in __actual_dictionaries:
                kwargs[argument_name] = value
            else:
                kwargs[argument_name] = construct_value(value)

        if merge_kwargs:
            kwargs.update(merge_kwargs)

        Logger.debug('state_storage: construct_value() calling {}({})'
                     .format(constructor_path, kwargs))
        return Constructor(**kwargs)

    else:
        # Should be correct type already from JSON
        if type(store_node) not in valid_construct_value_types:
            raise AssertionError('Object of type {} is not a valid value type'.format(type(store_node)))

        return store_node


    # if dictionary need to recurse

def construct_creature(store, **merge_kwargs):
    """Construct """
    constructor_names = store['info']['creature_constructors']
    creature_id = store['info']['id']

    if not constructor_names:
        raise InsufficientData('creature_constructors empty')

    Logger.debug('state_storage: construct_creature() id=%s, constructors=%s', creature_id, constructor_names)

    creature_part_name = constructor_names[0]
    merge_kwargs.update({'creature_id': creature_id, 'part_name': creature_part_name})
    creature = construct_value(store[creature_part_name], **merge_kwargs)

    creature_parts = store.keys()
    for name in constructor_names[1:]:
        if name in creature_parts:
            construct_value(store[name], creature=creature, part_name=name)
        else:
            Logger.debug('Creature %s missing part structure "%s"', creature_id, name)


    return creature



