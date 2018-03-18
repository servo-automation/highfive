from interface import IntegrationStore

import json
import os.path as path
import os
import shutil


class JsonStore(IntegrationStore):
    '''
    JSON store. This maintains a directory for each installation, and each key goes into a JSON file
    in that directory. This is chosen if `dump_path` key is specified in the config.
    '''

    def __init__(self, dump_path):
        super(JsonStore, self).__init__()
        self.dump_path = dump_path

    def get_installations(self):
        for dirname in os.listdir(self.dump_path):
            try:
                installation_id = int(dirname)
            except ValueError:      # skip if the name is not an integer
                continue
            self.logger.debug('Found installation %s in %r, adding it to queue',
                              installation_id, self.dump_path)
            yield installation_id

    def get_object(self, inst_id, key):
        data = {}
        parent = path.join(self.dump_path, str(inst_id))
        dump_path = path.join(parent, key)
        if path.isfile(dump_path):
            with open(dump_path, 'r') as fd:
                self.logger.debug('Loading JSON from %r', dump_path)
                data = json.load(fd)
        return data

    def remove_object(self, inst_id, key):
        parent = path.join(self.dump_path, str(inst_id))
        dump_path = path.join(parent, key)
        if path.isfile(dump_path):
            self.logger.debug('Removing file %r', dump_path)
            os.remove(dump_path)
        else:
            self.logger.error('Error removing file %r', dump_path)

    def write_object(self, inst_id, key, data):
        parent = path.join(self.dump_path, str(inst_id))
        if not path.isdir(parent):       # dir for each installation
            self.logger.debug('Creating %r for dumping JSONs', parent)
            os.mkdir(parent)
        dump_path = path.join(parent, key)
        with open(dump_path, 'w') as fd:
            self.logger.debug('Dumping JSON to %r', dump_path)
            json.dump(data, fd)
