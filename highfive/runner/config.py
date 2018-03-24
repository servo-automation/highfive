import json
import logging
import os
import os.path as path
import re

__LOGGERS = {}

def get_logger(name):
    '''
    `logger.getLogger()` creates a new instance for all calls. This makes sure that
    we always get the logger unique to a name.
    '''
    global __LOGGERS
    if __LOGGERS.get(name):
        return __LOGGERS[name]
    else:
        logger = logging.getLogger(name)
        __LOGGERS[name] = logger
        return logger


def init_logger(level=logging.DEBUG):
    '''
    Initializes the logger (in debug mode by default). This should be called
    when actually running highfive - otherwise, no logging!
    '''

    logging.basicConfig(level=level,
                        format='%(asctime)s %(levelname)s %(module)s - %(funcName)s: %(message)s',
                        datefmt="%Y-%m-%d %H:%M:%S")


def read_file(path):
    '''Yes, I know - it simply reads a file! The testsuite overrides this.'''

    with open(path, 'r') as fd:
        return fd.read()


class Configuration(object):
    '''
    Configuration object for highfive. This is passed around to the runner,
    API providers and other handlers. Once this is initialized, one of the loading
    methods should be called to load the configuration. This supports loading values
    from the environment.

    For example, if a key named "foo" has a value "ENV::BAR", then this function
    tries `os.environ.get('BAR')` and assigns the occurrences of "ENV::BAR" with
    the result. The value is JSON-encoded, so `None` will transform to `null`
    appropriately.
    '''
    def __init__(self):
        self.config = {}
        self.logger = get_logger(__name__)

    def load_from_file(self, config_path):
        '''Load configuration from the given path'''

        contents = read_file(config_path)
        return self.load_from_string(contents)

    def load_from_string(self, raw_config):
        '''Load configuration from the given raw string.'''

        matches = re.findall(r'"ENV::([A-Z_0-9]*)"', raw_config)
        for m in matches:   # Check and replace env variables (if any)
            if not os.environ.get(m):
                raise KeyError("%r not found in environment" % m)

            value = os.environ[m]
            encoded = json.dumps(value)
            self.logger.debug('Replacing env variable %s with %s' % (m, encoded))
            raw_config = raw_config.replace('"ENV::%s"' % m, encoded)

        config = json.loads(raw_config)
        try:
            self.initialize_defaults(config)
        except AttributeError as err:
            key = err.args[0].split("'")[-2]
            raise KeyError("Missing %r in configuration" % key)

    def initialize_defaults(self, config_dict):
        '''Checks the mandatory keys in config and initializes defaults (if required)'''

        for key, value in config_dict.iteritems():
            setattr(self, key, value)

        # poke the necessary properties
        self.pem_key = read_file(self.pem_key)
        _ = self.name, self.pem_key, self.secret, int(self.integration_id)

        handler_path = path.join(path.dirname(path.dirname(__file__)), 'event_handlers')
        all_events = filter(lambda p: path.isdir(path.join(handler_path, p)),
                            os.listdir(handler_path))

        defaults = [
            ('imgur_client_id', None),
            ('enabled_events', all_events),
            ('allowed_repos', []),
            ('collaborators', {}),
        ]

        for attr, value in defaults:
            try:
                getattr(self, attr)
            except AttributeError:
                setattr(self, attr, value)

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            return None
