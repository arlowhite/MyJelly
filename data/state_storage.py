__author__ = 'awhite'

# Singletonish module that keeps kivy stores open for reading/writing state.

import os.path as P
import os

from kivy.storage.jsonstore import JsonStore
from kivy.app import App
from kivy.logger import Logger
from datetime import datetime

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


def load_jelly_storage(jelly_id):
    if jelly_id is None or len(jelly_id) < 1:
        raise ValueError('Invalid jelly_id: %s', jelly_id)

    global jelly_stores
    if jelly_id not in jelly_stores:
        data_dir = get_jellies_dir()
        path = P.join(data_dir, jelly_id+'.json')

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
            store['info'] = {'created_datetime':datetime.utcnow().isoformat()}

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
            Logger.warning('Non json file in jellies: %s', filename)

    return jellies
