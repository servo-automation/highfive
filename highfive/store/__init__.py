from interface import IntegrationStore, InstallationStore
from json_store import JsonStore
from postgres_store import PostgreSqlStore

import os

def from_config(config):
    '''Try to load a store based on the configuration.'''

    if config['dump_path']:
        if not os.path.isdir(config.dump_path):
            os.makedirs(config.dump_path)
        return JsonStore(config.dump_path)
    elif config['database_url']:
        return PostgreSqlStore(config.database_url)

    return None
