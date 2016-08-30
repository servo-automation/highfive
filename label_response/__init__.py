import json

def check_labels(api):
    with open('config.json', 'r') as fd:
        config = json.load(fd)

    if not config['active']:
        return

    labels = config['labels']
    for label, comment in labels.items():
        if api.payload['label']['name'].lower() == label:
            api.post_comment(comment)

method = check_labels
