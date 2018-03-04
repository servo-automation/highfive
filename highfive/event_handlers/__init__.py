from event_handler import EventHandler

import imp
import json
import os
import os.path as path

__HANDLERS = {}

def get_handlers_for(event, cached=False, wrap_config=True):
    '''
    Get the handlers corresponding to an event.

    This function loads the (enabled) handlers, their configuration files, and yields their paths
    along with the handler classes. The caller should pass the `APIProvider` interface to the
    yielded lambda function to actually initialize the handlers.

    If `cached` is enabled, then this iterates over the cached handlers. It assumes that
    the caller has already loaded the handlers using `load_handlers` function.

    If `wrap_config` is enabled, then the loader returns the handler wrapped in a lambda,
    so that the caller doesn't have to worry about the handler config by themselves.
    '''

    if cached:
        global __HANDLERS
        for components in __HANDLERS.get(event, []):
            if wrap_config and len(components) == 3:
                handler_dir, handler_config, handler = components
                yield (handler_dir, lambda api: handler(api, handler_config))
            else:
                # At this point, if it's already a lambda-wrapped handler, then it has already
                # lost its context. This happens when `wrap_config=True` in `load_handlers_using`
                # function below.
                yield components
        return

    root = path.dirname(path.dirname(__file__))
    event_dir = path.join(root, 'event_handlers', event)
    if not path.isdir(event_dir):
        return

    for handler_name in os.listdir(event_dir):
        handler_dir = path.join(event_dir, handler_name)
        handler_path = path.join(handler_dir, '__init__.py')
        config_path = path.join(handler_dir, 'config.json')

        # Every handler should have its own 'config.json'
        if not (path.exists(handler_path) and path.exists(config_path)):
            continue

        with open(config_path, 'r') as fd:
            handler_config = json.load(fd)

        module = imp.load_module('highfive.event_handlers.%s.%s' % (event, handler_name),
                                 None, handler_dir,
                                 ('', '', imp.PKG_DIRECTORY))
        if wrap_config:
            yield (handler_dir, lambda api: module.handler(api, handler_config))
        else:
            yield (handler_dir, handler_config, module.handler)


def load_handlers_using(config):
    '''
    Load and cache the existing handlers. This iterates over all the events from the configuration
    object and loads the handlers in memory. After this, `get_handlers_for` function can be called
    with `cached=True`
    '''

    count = 0
    global __HANDLERS

    for event in config.enabled_events:
        __HANDLERS[event] = []
        # NOTE: Don't ever set `wrap_config=True`! All hell breaks loose!
        # (You can try running the tests after setting it)
        for components in get_handlers_for(event, wrap_config=False):
            __HANDLERS[event].append(components)
            count += 1

    print 'Loaded', count, 'handlers.'
