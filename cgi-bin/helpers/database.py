from methods import ROOT, get_logger

import os, json

DB_JSON_LEN = 8192

class JsonStore(object):
    def __init__(self, config):
        self.logger = get_logger(__name__)
        self.dump_path = config['dump_path']

    def get_installations(self):
        for _id in map(int, os.listdir(self.dump_path)):
            self.logger.debug('Found installation %s in %r, adding it to queue', _id, self.dump_path)
            yield _id

    def get_obj(inst_id, path):
        data = {}
        parent = os.path.join(self.dump_path, str(inst_id))
        if not os.path.isdir(parent):       # dir for each installation
            self.logger.debug('Creating %r for dumping JSONs', parent)
            os.makedirs(parent)
        dump_path = os.path.join(parent, *path)
        if os.path.isdir(dump_path):
            return os.listdir(dump_path)
        elif os.path.isfile(dump_path):
            with open(dump_path, 'r') as fd:
                self.logger.debug('Loading JSON from %r', dump_path)
                data = json.load(fd)
        return data

    def write_obj(self, data, inst_id, path):
        parent = os.path.join(self.dump_path, str(inst_id))
        dump_path = os.path.join(parent, *path)
        stem, _base = os.path.split(dump_path)
        if not os.path.isdir(stem):
            os.makedirs(stem)           # recursively create dirs
        with open(dump_path, 'w') as fd:
            self.logger.debug('Dumping JSON to %r', dump_path)
            json.dump(data, fd)

def create_db(config):
    return JsonStore(config)
