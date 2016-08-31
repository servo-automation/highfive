
def check_labels(api, config):
    if api.payload['action'] != 'labeled':
        return

    # FIXME: should this be configured for individual repos? (like 'label_notify')
    labels = config.get('labels', [])
    for label, comment in labels.items():
        if api.payload['label']['name'].lower() == label:
            api.post_comment(comment)

methods = [check_labels]
