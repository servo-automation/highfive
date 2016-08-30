import json

def check_labels(api, config):
    if not config.get('active'):
        return

    labels = config.get('labels', [])
    for label, comment in labels.items():
        if api.payload['label']['name'].lower() == label:
            api.post_comment(comment)

methods = [check_labels]
