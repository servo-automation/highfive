import imp, json, logging, os, re

ROOT = os.path.dirname(os.path.dirname(__file__))
HANDLERS_DIR = os.path.join(ROOT, 'handlers')
AVAILABLE_EVENTS = filter(lambda p: os.path.isdir(os.path.join(HANDLERS_DIR, p)),
                          os.listdir(HANDLERS_DIR))
LOGGERS = {}

with open(os.path.join(ROOT, 'collaborators.json'), 'r') as fd:
    COLLABORATORS = json.load(fd)
with open(os.path.join(ROOT, 'config.json'), 'r') as fd:
    CONFIG = json.load(fd)
    if not os.path.exists(CONFIG['dump_path']):
        os.mkdir(CONFIG['dump_path'])

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


def find_reviewers(comment):
    '''
    If the user had specified the reviewer(s), then return the name(s),
    otherwise return None. It matches all the usernames following a
    review request.

    For example,
    "r? @foo r? @bar and cc @foobar"
    "r? @foo I've done blah blah r? @bar for baz"

    Both these comments return ['foo', 'bar']
    '''
    return re.findall('r\? @([A-Za-z0-9]+)', str(comment), re.DOTALL)


def join_names(names):
    ''' Join multiple words in human-readable form'''
    if len(names) == 1:
        return names.pop()
    elif len(names) == 2:
        return '{} and {}'.format(*names)
    elif len(names) > 2:
        last = names.pop()
        return '%s and %s' % (', '.join(names), last)
    return ''


def get_path_parent(obj, match=[], get_obj=lambda item: item):
    '''
    Recursively traverse through the dictionary to find a matching path.
    Once that's found, get the parent key which triggered that match.

    >>> d = {'a': {'b': {'c': {'d': 1}, {'e': 2}}}}
    >>> node = get_path_parent(d, ['c', 'e'])
    >>> print node
    {'c': {'e': 2, 'd': 1}}
    >>> node['c']['e']
    2

    It returns the (parent) node on which we can call those matching keys. This is
    useful when we're sure about how a path of a leaf ends, but not how it begins.

    An optional method specifies how to address the object i.e., whether to do it
    directly, or call another method to get the underlying object from the wrapper.
    (the method is overridden when we use JsonCleaner's NodeMarker type)
    '''
    sep = '->'
    if not match:
        return

    def get_path(obj, match_path, path=''):
        item = get_obj(obj)
        if hasattr(item, '__iter__'):
            iterator = xrange(len(item)) if isinstance(item, list) else item
            for key in iterator:
                new_path = path + str(key) + sep
                if new_path.endswith(match_path):
                    return new_path.rstrip(sep)

                result = get_path(item[key], match_path, new_path)
                if result:
                    return result

    match_path = sep.join(match) + sep
    result = get_path(obj, match_path)
    if not result:      # so that we don't return None
        return {}

    keys = result.split(sep)[:-len(match)]
    if not keys:        # special case - where the path is a prefix
        return obj

    parent = keys.pop(0)
    node = get_obj(obj)[parent]

    for child in keys:      # start from the root and get the parent
        node = get_obj(node)[child]

    return node


def get_handlers(event_name, sync=False):
    '''
    Execute all the handlers corresponding to the events (specified in the config) and
    yield the methods that process the payload
    '''
    event_dir = os.path.join(HANDLERS_DIR, event_name)
    if not os.path.isdir(event_dir):
        return

    for handler_name in sorted(os.listdir(event_dir)):
        handler_dir = os.path.join(event_dir, handler_name)
        handler_path = os.path.join(handler_dir, '__init__.py')
        config_path = os.path.join(handler_dir, 'config.json')

        # Every handler should have its own 'config.json'
        if os.path.exists(handler_path) and os.path.exists(config_path):
            with open(config_path, 'r') as fd:
                handler_config = json.load(fd)

            if not handler_config.get('active'):    # per-handler switch
                continue

            sync_handler = handler_config.get('sync')
            if (sync and not sync_handler) or (sync_handler and not sync):
                continue

            module = imp.load_module('handlers.' + handler_name, None, handler_dir,
                                     ('', '', imp.PKG_DIRECTORY))
            yield (handler_dir,
                   lambda api, *args: module.payload_handler(api, handler_config, *args))
