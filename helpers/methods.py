import json, os

HANDLERS_DIR = 'handlers'


def get_matching_path_parent(obj, match=[]):
    '''
    Recursively traverse through the dictionary to find a matching path.
    Once that's found, get the parent key which triggered that match.

    >>> d = {'a': {'b': {'c': {'d': 1}, {'e': 2}}}}
    >>> node = get_matching_path_parent(d, ['c', 'e'])
    >>> print node
    {'c': {'e': 2, 'd': 1}}
    >>> node['c']['e']
    2

    It returns the (parent) node on which we can call those matching keys. This is
    useful when we're sure about how a path of a leaf ends, but not how it begins.
    '''
    sep = '->'
    if not match:
        return

    def get_paths(obj, match_path, path=''):
        if hasattr(obj, '__iter__'):
            iterator = xrange(len(obj)) if isinstance(obj, list) else obj.keys()
            for key in iterator:
                new_path = path + str(key) + sep
                if match_path in new_path:
                    return new_path.rstrip(sep)

                result = get_paths(obj[key], match_path, new_path)
                if result:
                    return result

    match_path = sep.join(match) + sep
    result = get_paths(obj, match_path)
    if not result:      # so that we don't return None
        return {}

    keys = result.split(sep)[:-len(match)]
    if not keys:        # special case - where the path is a prefix
        return obj

    parent = keys.pop(0)
    node = obj[parent]

    for child in keys:      # start from the root and get the parent
        node = node[child]

    return node


def get_handlers(accepted_events):
    '''
    Execute all the handlers corresponding to the events (specified in the config) and
    yield the methods that process the payload
    '''
    for event_name in sorted(os.listdir(HANDLERS_DIR)):
        if event_name not in accepted_events:
            continue

        event_dir = os.path.join(HANDLERS_DIR, event_name)
        if not os.path.isdir(event_dir):
            continue

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

                execfile(handler_path)
                for method in locals().get('methods', []):
                    yield handler_dir, lambda api: method(api, handler_config)
