from ..runner.config import get_logger

class IntegrationStore(object):
    '''
    All handlers live/breathe on JSON data. This is an interface for the store globally used by all
    installations. The implementor is only used by the runner and is exposed to the handlers
    only through InstallationStore.
    '''

    def __init__(self, config):
        self.logger = get_logger(__name__)
        self.config = config

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


class InstallationStore(IntegrationStore):
    '''Wrapper for IntegrationStore, to keep installation IDs out of handlers' reach.'''

    def __init__(self, inst_id, config):
        self.logger = get_logger(__name__)
        self._inst_id = inst_id

    def get_object(self, key):
        return super(InstallationStore, self).get_object(self._inst_id, key)

    def remove_object(self, key):
        return super(InstallationStore, self).remove_object(self._inst_id, key)

    def write_object(self, key, value):
        return super(InstallationStore, self).write_object(self._inst_id, key)
