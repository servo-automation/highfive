from ..runner.config import get_logger

class IntegrationStore(object):
    '''
    All handlers live/breathe on JSON data. This is an interface for the store globally used by all
    installations. The implementors are only used by the runner, which exposes the store to the
    handlers only through the InstallationStore wrapper.
    '''

    def __init__(self):
        self.logger = get_logger(__name__)

    def get_installations(self):
        '''
        Get the installations from the dump path. This should only return a list of integers
        representing installations.
        '''

        raise NotImplementedError

    def get_object(self, inst_id, key):
        '''Get the data for a given key for an installation.'''

        raise NotImplementedError

    def remove_object(self, inst_id, key):
        '''Remove the data associated with the given key from an installation.'''

        raise NotImplementedError

    def write_object(self, inst_id, key, data):
        '''
        Write the data for a key in an installation. This should also handle the case
        when an installation doesn't exist.
        '''

        raise NotImplementedError


class InstallationStore(object):
    '''Wrapper for IntegrationStore, to keep installation IDs out of handlers' reach.'''

    def __init__(self, store, inst_id):
        self.store = store
        self._inst_id = inst_id

    def get_object(self, key):
        return self.store.get_object(self._inst_id, key)

    def remove_object(self, key):
        return self.store.remove_object(self._inst_id, key)

    def write_object(self, key, data):
        return self.store.write_object(self._inst_id, key, data)
