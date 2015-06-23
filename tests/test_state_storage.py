__author__ = 'awhite'

import pytest

from data.state_storage import *

# from main import MyJellyApp

@pytest.fixture
def creature_store(tmpdir):
    filepath = str(tmpdir.join('creature_store.json').realpath())
    return CreatureStore(filepath, creature_id='test')

def test_instance_name_sort_key():
    assert instance_name_sort_key('foo/3') == 3
    assert instance_name_sort_key('foo/555') == 555
    assert instance_name_sort_key('group/1/') == 1
    assert instance_name_sort_key('group/1234/') == 1234
    assert instance_name_sort_key('group/1234/4') == 4
    assert instance_name_sort_key('group/1234/33') == 33

def test_by_reference(creature_store):
    """verify store behavior
    - defensive copies?
    - acts like dict
    - put and [] behave the same
    """
    store = creature_store

    assert 'foo' not in store

    obj = {'x': 5}
    store['foo'] = obj

    assert obj is store['foo']

    assert store['foo']['x'] == 5

    retrieved = store['foo']
    # No defensive copy
    assert retrieved is store['foo']
    assert retrieved['x'] == 5

    retrieved['y'] = 3
    assert store['foo']['y'] == 3

    # Merging behavior I overrode
    # This may change...
    merge = {'y': 7}
    store['foo'] = merge
    # Still original object
    assert store['foo'] is obj
    assert obj == {'x':5, 'y': 7}

    # Using store_put() there's no copy
    o2 = {'z': 1}
    store.store_put('bar', o2)
    assert o2 is store['bar']

def test_missing_group(creature_store):
    with pytest.raises(ValueError):
        creature_store.add_part('group/0/')

def test_bad_values(creature_store):
    with pytest.raises(ValueError):
        creature_store.add_part('foo/0')

    with pytest.raises(ValueError):
        creature_store.add_part('foo/0/23/')

    with pytest.raises(ValueError):
        creature_store.add_part('')

    with pytest.raises(ValueError):
        creature_store.add_part('/')

    with pytest.raises(ValueError):
        creature_store.add_part('/0/')

    with pytest.raises(ValueError):
        creature_store.new_group('')

# FIXME
# def test_construct_creature(self):
#     os.chdir('..')  # Image paths are relative to project root
#     app = MyJellyApp()
#     app.run()
#
#     jelly_id = 'f6b069974318417183c7f820b86d7b99'
#     store = load_jelly_storage(jelly_id)
#     jelly = construct_creature(store)

def test_adding_parts(creature_store):
    s = creature_store
    part_name = s.add_part('foo')
    assert part_name == 'foo/0'
    assert s[part_name] == {}

    part_name = s.add_part('foo')
    assert part_name == 'foo/1'

    assert s.parts['foo'] == ['foo/0', 'foo/1']

def test_adding_deleting_group(creature_store):
    store = creature_store
    # How to determine this name...
    # can't use add_part because it mutates store

    group_name = store.new_group('tentacles')
    assert group_name == 'tentacles/0/'
    assert 'tentacles/' in store.groups
    assert len(store.groups['tentacles/']) == 1
    assert store.groups['tentacles/'] == ['tentacles/0/']
    assert 'tentacles/0/' in store.parts
    # Should only be info element
    assert len(store) == 1
    assert isinstance(store.parts['tentacles/0/'], list)

    name = store.add_part(group_name)
    assert name == 'tentacles/0/0'
    assert store[name] == {}

    name = store.add_part(group_name)
    assert name == 'tentacles/0/1'
    assert store[name] == {}
    assert store.parts['tentacles/0/'] == \
           ['tentacles/0/0', 'tentacles/0/1']

    assert len(store) == 3  # info + 2 parts

    group_name = store.new_group('tentacles')
    assert group_name == 'tentacles/1/'
    assert 'tentacles/1/' in store.parts
    assert store.groups['tentacles/'] == ['tentacles/0/', 'tentacles/1/']

    store.new_group('tentacles')

    part = store.add_part('tentacles/0/')
    assert part == 'tentacles/0/2'
    assert len(store.parts['tentacles/0/']) == 3

    # Just continue with deleting test here
    # Delete part within a group
    delete_part = 'tentacles/0/1'
    del store[delete_part]
    assert store.parts['tentacles/0/'] == \
           ['tentacles/0/0', 'tentacles/0/2']
    assert delete_part not in store

    part = store.add_part('tentacles/0/')
    assert part == 'tentacles/0/3'

    group_parts = ['tentacles/0/0', 'tentacles/0/2', 'tentacles/0/3']
    delete_group = 'tentacles/0/'
    assert store.parts[delete_group] == group_parts
    store.creature_constructors.append(delete_group)

    assert delete_group in store.groups['tentacles/']

    store.delete_group(delete_group)
    assert delete_group not in store.groups['tentacles/']
    assert delete_group not in store.parts
    for key in group_parts:
        assert key not in store
    assert delete_group not in store.creature_constructors


    # Delete root group
    delete_group = 'tentacles/'
    store.creature_constructors.append(delete_group)
    store.delete_group(delete_group)
    assert delete_group not in store.creature_constructors
    assert delete_group not in store.groups
    assert len(store) == 1 # just info again
    assert len(store.parts) == 0
    assert len(store.groups) == 0
    assert len(store.creature_constructors) == 0

def test_deleted_part(creature_store):
    s = creature_store
    name = 'foo'
    s.add_part(name)
    key = s.add_part(name)
    s.add_part(name)

    s.creature_constructors.append(key)

    # Before: in all these locations
    assert key in s
    assert key in s.creature_constructors
    assert key in s.parts[name]

    del s[key]
    assert key not in s
    assert key not in s.creature_constructors
    assert key not in s.parts[name]

    # Next added part should increment from last instead of taking deleted spot
    key = s.add_part(name)
    assert key == 'foo/3'

