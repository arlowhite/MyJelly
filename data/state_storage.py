__author__ = 'awhite'

# Singletonish module that keeps kivy stores open for reading/writing state.

import os.path as P
import os
from uuid import uuid4

from kivy.storage.jsonstore import JsonStore
from kivy.logger import Logger
from kivy.utils import reify
from datetime import datetime

# Mapping of class paths to classes allowed to be constructed from JSON
constructable_members = {}

from misc.exceptions import InsufficientData

jelly_stores = {}
app_store = None
# To be set by main
user_data_dir = None

class LazyJsonStore(JsonStore):
    # Does not sync right away
    # puts merge by default
    # TODO Better to have a merge function? Think about API; maybe refactor
    # Besides, only root level dictionary merges, everything else doesn't

    def store_put(self, key, value):
        """Merges with existing data
        Warning: this means the dicts are the same object on first put (assignment),
        but not on future puts.
        """
        if key in self._data:
            # Merge dictionaries instead of replacing
            self._data[key].update(value)

        else:
            self._data[key] = value

        self._is_changed = True
        return True

    def merge(self, *keypath, **kwargs):
        """Merge given kwargs into the dictionary at the given path.
        :param keypath equivalent to store['key1']['key2']
        :raises KeyError if invalid keypath
        """
        d = self._data
        for key in keypath:
            d = d[key]

        if not isinstance(d, dict):
            raise AssertionError('Object at keypath {} is {} not dict'.format(keypath, type(d)))

        d.update(kwargs)

    # Override so new dict object isn't created
    def __setitem__(self, key, values):
        # Not sure why this enforcement exists, but keeping it for now
        if not isinstance(values, dict):
            raise Exception('Only dict are accepted for the store[key] = dict')

        # Replacing self.put(key, **values)
        self.store_put(key, values)

    # Don't store_sync every time
    def put(self, key, **values):
        """Note: This inevitably creates a new dict"""
        return self.store_put(key, values)

    def delete(self, key):
        return self.store_delete(key)

    # This isn't implemented in baseclass for some reason
    # TODO report to Kivy
    def __delitem__(self, key):
        self.store_delete(key)

def instance_name_sort_key(x):
    """All part/group instance names should end with /# or /#/
     This key function compares on that #"""
    if x[-1] == '/':
        # group type key group/#/
        return int(x[x.rfind('/', 0, -1) + 1:-1])
    else:
        return int(x[x.rfind('/') + 1:])

class CreatureStore(LazyJsonStore):
    """Provides correct manipulation of creature part_names and useful methods.
    Do not modify part_names directly, use methods.
    """

    def __init__(self, filename, creature_id=None, **kwargs):
        super(CreatureStore, self).__init__(filename, **kwargs)

        if '_info' not in self:
            self._initialize_new(creature_id)

        # Convenience properties
        info = self.info
        self.creature_id = info['id']

        const = info['creature_constructors']
        assert isinstance(const, list)
        self.creature_constructors = const

    # NotE: decided NOT to put trailing slash on group names so that API's
    # return values can feed into other methods arguments
    @reify
    def parts(self):
        """Mapping of base part/group names to lists of instance names.
        (i.e. all names in lists are valid part store keys)
        part > [part/0, part/1, ...]
        group/0/ > [group/0/0, group/0/1, ...]

        :returns sorted list of instance names
        :raises KeyError if name not found
        """
        parts = {}
        groups = {}

        # Go through all part instance names in the store
        for name in self:
            if name[0] == '_':
                # metadata such as _info
                continue

            num_slashes = name.count('/')
            last_slash_index = name.rfind('/')
            if num_slashes == 1:
                key = name[:last_slash_index]
                if key not in parts:
                    parts[key] = []

                parts[key].append(name)
            elif num_slashes == 2:
                # group/0 to group/0/0
                group_instance_name = name[:last_slash_index + 1]
                if group_instance_name not in parts:
                    parts[group_instance_name] = [name]
                else:
                    parts[group_instance_name].append(name)

                # group to group/0
                key = group_instance_name[:group_instance_name.rfind('/', 0, -1) + 1]
                if key not in groups:
                    groups[key] = [group_instance_name]

                else:
                    # avoid duplicating group instance names in list
                    group_instances = groups[key]
                    if group_instance_name not in group_instances:
                        group_instances.append(group_instance_name)

            else:
                raise ValueError("Invalid store name '{}' has {} slashes"
                                 .format(name, num_slashes))

        for l in parts.viewvalues():
            l.sort(key=instance_name_sort_key)

        self.__groups = groups

        return parts

    @reify
    def groups(self):
        """Mapping of base group name to list of group instance names.
        Note: These are invalid store keys, use self.parts to get part instances.
        group/ > [group/0/, group/1/, ...]
        """
        # Computation is done in parts()
        p = self.parts
        groups = self.__groups

        # Really lazy and not sorting until now
        for l in groups.viewvalues():
            l.sort(key=instance_name_sort_key)

        del self.__groups
        return groups

    @property
    def info(self):
        return self['_info']

    def _initialize_new(self, creature_id):
        "called when info not already in store"
        if creature_id is None or len(creature_id) == 0:
            raise ValueError('creature_id must be provided when creating a new store')

        self['_info'] = {'created_datetime': datetime.utcnow().isoformat(),
                          'id': creature_id, 'creature_constructors': []}

    def store_delete(self, deleted_key):
        r_val = LazyJsonStore.store_delete(self, deleted_key)
        if deleted_key[0] == '_':
            # Not a part/group key
            return

        # assuming deleted_key is a part_instance_name
        try:
            self.creature_constructors.remove(deleted_key)
        except ValueError:
            # May not be in creature_constructors
            pass

        # 'part/#' or 'group/#/#'
        # In either case, deleting from parts
        key = deleted_key[:deleted_key.rfind('/') + 1]
        num_slashes = key.count('/')
        if num_slashes == 1:
            # remove trailing slash from part
            key = key[:-1]

        else:
            assert num_slashes == 2

        self.parts[key].remove(deleted_key)

        return r_val

    # Simplest solution is not to bother with nesting lists, etc.
    # Don't need sorting
    def add_part(self, name):
        """Add part_name to store and creature_constructors.
        :param name arbitrary name for the part or name of existing group
        If this is the first part with this name, the actual store key
        will have a '/0' suffix
        Otherwise, the number will be the current highest part plus one.

        If part_name ends with a slash, it indicates a group and must be an existing
        group_name created by new_group, i.e. group/0/

        value in store will be set to a new dict

        TODO maybe return tuple with value?
        :returns part_instance_name
        """
        if len(name) == 0:
            raise ValueError('name is a blank string!')

        slash_index = name.rfind('/')

        if slash_index != -1:
            # Last slash should be trailing, verify valid group i.e. group/0/
            if slash_index != len(name) - 1:
                # This would cause problems when parsing groups from store on load
                raise ValueError("Group part_name '{}' does not end with /".format(name))

            if name.count('/') != 2:
                raise ValueError("Group name does not have two slashes '{}' expected group/0/".format(name))

            # group should be a within parts
            if name not in self.parts:
                raise ValueError('part_name looks like a group, but group not created')

            # Don't need to add a slash later
            instance_str_format = '{}{}'

        else:
            # No slashes in name
            instance_str_format = '{}/{}'

        # This will reuse deleted part_instance_names
        # for num in count():
        #     part_instance_name = '{}/{}'.format(part_name, num)
        #     if part_instance_name not in self:
        #         # Found an available name
        #         break

        try:
            existing_parts = self.parts[name]
        except KeyError:
            existing_parts = []
            self.parts[name] = existing_parts

        num = 0
        if len(existing_parts) > 0:
            # last number plus one
            num = instance_name_sort_key(existing_parts[-1]) + 1
            assert num > 0

        part_instance_name = instance_str_format.format(name, num)

        self[part_instance_name] = {}
        self.parts[name].append(part_instance_name)

        return part_instance_name

    def new_group(self, group_name):
        """Create a new group.
        :param group_name name of the group to create (optional trailing slash)
        :returns 'group_name/#/'
        """
        if len(group_name) == 0:
            raise ValueError('group_name is a blank string!')

        # Make sure group_name has trailing slash for key lookups
        if group_name[-1] != '/':
            group_name += '/'

        if group_name.count('/') != 1:
            raise ValueError("Invalid slashes in group_name '{}'".format(group_name))

        groups = self.groups
        try:
            existing = groups[group_name]
        except KeyError:
            existing = []
            groups[group_name] = existing

        num = 0
        if len(existing) > 0:
            # last group number plus one
            num = instance_name_sort_key(existing[-1]) + 1
            assert num > 0

        group_instance_name = '{}{}/'.format(group_name, num)
        groups[group_name].append(group_instance_name)
        self.parts[group_instance_name] = []

        return group_instance_name

    def delete_group(self, group_name):
        """Delete a group and all of its parts
        :param group_name group/#/ or group/
        """
        if group_name[-1] != '/':
            group_name += '/'

        num_slashes = group_name.count('/')
        if num_slashes > 2:
            raise ValueError('More than 2 slashes in group_name "{}"'.format(group_name))

        if num_slashes == 2:
            # subgroup
            # delete all parts (copy list because it is modified by del)
            for part in self.parts[group_name][:]:
                Logger.debug('state_storage: delete_group({}) delete part "{}"'.format(group_name, part))
                del self[part]

            del self.parts[group_name]

            # delete self from groups
            key = group_name[:group_name.rfind('/', 0, -1) + 1]
            self.groups[key].remove(group_name)

        else:
            assert num_slashes == 1
            for subgroup in self.groups[group_name][:]:
                self.delete_group(subgroup)

            del self.groups[group_name]

        try:
            self.creature_constructors.remove(group_name)
        except ValueError:
            pass


    def part_kwargs(self, part_instance_name):
        raise NotImplementedError()


    def _sort_name_into_constructors(self):
        raise NotImplementedError()

def get_jellies_dir():
    assert user_data_dir is not None
    jellies = P.join(user_data_dir, 'jellies')
    if not P.exists(jellies):
        os.mkdir(jellies)

    return jellies

def load_app_storage():
    assert user_data_dir is not None
    global app_store
    if app_store is None:
        Logger.debug('state_storage: Opening app.json')
        app_store = LazyJsonStore(P.join(user_data_dir, 'app.json'))

    return app_store


def __jelly_json_path(creature_id):
    return P.join(get_jellies_dir(), creature_id+'.json')

# This should probably be somewhere else (maybe jelly.py?),
# but this is as good a spot as any for now.
def new_jelly():
    """Creates a new jelly store and id and returns the id"""

    # TODO If image used before, ask if want to open that Jelly
    # TODO Copy image file for safe keeping?
    # TODO check if image file
    creature_id = uuid4().hex
    jelly = load_jelly_storage(creature_id, new=True)

    jelly.store_sync()  # As soon as image is saved, save jelly state
    return creature_id

def load_jelly_storage(creature_id, new=False):
    """Load the store from the jellies directory with the given creature_id
     (may be from cached)
    :param creature_id: id of the Creature to load.
    :param new: whether to create a new store.
    :rtype: CreatureStore
    :raises ValueError if store does not exist and new=False
    """
    if creature_id is None or len(creature_id) < 1:
        raise ValueError('Invalid creature_id: %s', creature_id)

    # TODO use kivy.cache?
    if creature_id not in jelly_stores:
        path = __jelly_json_path(creature_id)

        new_store = not P.exists(path)

        if new_store:
            if not new:
                raise ValueError('No creature with id %s'%creature_id)

            Logger.debug('state_storage: Creating new store %s', path)
        else:
            if new:
                raise AssertionError('new specified but creature already exists {}'.format(creature_id))

            Logger.debug('state_storage: Opening %s', path)

        try:
            store = CreatureStore(path, creature_id=creature_id)
            # CreatureStore will initialize if no info set
        except ValueError:
            # FIXME This is bad, should capture bad file for release
            Logger.error('Failed to load JsonStore from file %s', path)
            #os.remove(path)
            raise

        jelly_stores[creature_id] = store

    return jelly_stores[creature_id]

def load_all_jellies():
    jellies_dir = get_jellies_dir()
    # TODO sort jellies? last access?
    jellies = []
    for filename in os.listdir(jellies_dir):
        creature_id, ext = P.splitext(filename)

        if ext == '.json':
            try:
                jellies.append(load_jelly_storage(creature_id))
            except ValueError:
                Logger.error('Failed to load %s, will not be in all_jellies list', creature_id)
                pass
        else:
            Logger.warning('state_storage: Non json file in jellies "%s"', filename)

    return jellies

def delete_jelly(creature_id):
    if creature_id in jelly_stores:
        del jelly_stores[creature_id]

    path = __jelly_json_path(creature_id)
    if P.exists(path):
        Logger.info("Removing Jelly %s JSON: %s", creature_id, path)
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
        raise AssertionError('Expect just one key that is a Constructor module path, given {}'
                             .format(object.keys()))

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
    constructor_names = store.creature_constructors
    creature_id = store.creature_id

    if not constructor_names:
        raise InsufficientData('creature_constructors empty')

    Logger.debug('state_storage: construct_creature() id=%s, constructors=%s', creature_id, constructor_names)

    creature_part_name = constructor_names[0]
    merge_kwargs.update({'creature_id': creature_id, 'part_name': creature_part_name})
    creature = construct_value(store[creature_part_name], **merge_kwargs)

    # Maybe different parts can ellect to be the main Creature part?
    # For example, gooey without bell?
    # But that logic needs to be somewhere, so no?
    # CiliatedCreature would just make anything move for example

    creature_parts = store.keys()
    for name in constructor_names[1:]:
        if name in creature_parts:
            construct_value(store[name], creature=creature, part_name=name)
        else:
            Logger.debug('Creature %s missing part structure "%s"', creature_id, name)


    return creature



