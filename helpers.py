import json, os


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

    match_path = sep.join(match)
    result = get_paths(obj, match_path)
    if not result:
        return {}

    points = result.split(sep)[:-len(match)]
    if not points:
        return obj

    key = points.pop(0)
    node = obj[key]

    for key in points:
        node = node[key]

    return node


def get_handlers():
    '''
    Execute all the handlers and yield the methods that process the payload
    '''
    for event_name in sorted(os.listdir('handlers')):
        event_dir = os.path.join('handlers', event_name)
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
                    yield lambda api: method(api, handler_config)
