import json, os, re

HANDLERS_DIR = 'handlers'


class Shared(object):
    '''Methods required by the handlers in the submodules'''
    def find_reviewers(self, comment):
        '''
        If the user had specified reviewer(s), return the username(s),
        otherwise return None.

        For example, both 'r? @foo @bar,@foobar' and 're? @foo,@bar, @foobar'
        return ['foo', 'bar', 'foobar']
        '''
        result = re.search(r'r[eviw]*[\?:\- ]*@([@a-zA-Z0-9\-, ]*)', str(comment))
        if result:
            reviewers = result.group(1)
            names = filter(lambda s: s, reviewers.split('@'))
            return map(lambda name: name.strip(' ,'), names)


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


def get_handlers(accepted_events):
    '''
    Execute all the handlers corresponding to the events (specified in the config) and
    yield the methods that process the payload
    '''
    for event_name in sorted(accepted_events):
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

                with open(handler_path, 'r') as fd:
                    source = fd.read()
                    exec source in locals()

                for method in methods:
                    yield handler_dir, lambda api: method(api, handler_config)
