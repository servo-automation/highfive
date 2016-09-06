
def check_labels(api, config):
    repos = config.get('repos')
    if not (repos and api.payload.get('action') == 'labeled'):
        return

    for labels in api.get_matches_from_config(repos):
        for label, comment in labels.items():
            if api.payload['label']['name'].lower() == label:
                api.post_comment(comment)


methods = [check_labels]
