import os


def get_handlers():
    for event_name in sorted(os.listdir('handlers')):
        event_dir = os.path.join('handlers', event_name)
        if not os.path.isdir(event_dir):
            continue

        for handler_name in sorted(os.listdir(event_dir)):
            path = os.path.join(event_dir, handler_name, '__init__.py')
            if os.path.exists(path):
                execfile(path)
                yield locals().get('method', lambda api: None)
