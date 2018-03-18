from highfive.runner import Configuration
from highfive.store import JsonStore

from unittest import TestCase

import json
import os.path as path
import os
import shutil

class JsonStoreTests(TestCase):
    def test_get_existing_installations(self):
        '''Test getting existing installations from store.'''

        config = Configuration()
        config.dump_path = path.dirname(__file__)
        store = JsonStore(config)
        inst_id = 5127
        self.assertEqual(list(store.get_installations()), [])
        os.mkdir(path.join(config.dump_path, str(inst_id)))
        self.assertEqual(list(store.get_installations()), [inst_id])
        os.rmdir(path.join(config.dump_path, str(inst_id)))

    def test_writing_getting_and_removing_objects(self):
        '''Test writing an object to file, getting it back and removing it entirely from the store.'''

        config = Configuration()
        config.dump_path = path.dirname(__file__)
        store = JsonStore(config)
        inst_id = 5003
        data = {'key': 'value'}
        # This will (should!) automatically create a dir for installtion and put foobar inside it
        store.write_object(inst_id, 'foobar', data)
        obj_path = path.join(config.dump_path, str(inst_id), 'foobar')

        storeData = store.get_object(inst_id, 'foobar')
        self.assertEqual(data, storeData)
        with open(obj_path) as fd:
            self.assertEqual(json.load(fd), data)

        store.remove_object(inst_id, 'foobar')
        # This will work only if the previous line succeeds
        os.rmdir(path.join(config.dump_path, str(inst_id)))
