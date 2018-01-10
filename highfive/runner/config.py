import json
import logging
import os
import re

LOGGERS = {}

def get_logger(name):
    '''
    `logger.getLogger()` creates a new instance for all calls. This makes sure that
    we always get the logger unique to a name.
    '''
    global LOGGERS
    if LOGGERS.get(name):
        return LOGGERS[name]
    else:
        logger = logging.getLogger(name)
        LOGGERS[name] = logger
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
    '''Yes, I know - it simply reads a file!'''

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
            value = os.environ.get(m)
            encoded = json.dumps(value)
            self.logger.debug('Replacing env variable %s with %s' % (m, encoded))
            raw_config = raw_config.replace('"ENV::%s"' % m, encoded)

        self.config = json.loads(raw_config)

    def __getitem__(self, key):
        '''Get the value corresponding to the key from the underlying config dict.'''

        return self.config.get(key)
