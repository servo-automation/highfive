from interface import IntegrationStore, InstallationStore
from json_store import JsonStore
from postgres_store import PostgreSqlStore

def from_config(config):
    '''Try to load a store based on the configuration.'''

    if config['dump_path']:
        return JsonStore(config.dump_path)
    elif config['database_url']:
        return PostgreSqlStore(config.database_url)

    return None
