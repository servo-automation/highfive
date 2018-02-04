from event_handler import EventHandler

import imp
import json
import os
import os.path as path

def get_handlers(event):
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

        if not handler_config.get('active'):    # per-handler switch
            continue

        module = imp.load_module('highfive.event_handlers.%s.%s' % (event, handler_name),
                                 None, handler_dir,
                                 ('', '', imp.PKG_DIRECTORY))
        yield (handler_dir, module.handler)
