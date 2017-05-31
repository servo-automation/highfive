
def payload_handler(api, config):
    repos = config.get('repos')
    if not (repos and api.payload.get('action') == 'labeled'):
        return

    repo_config = api.get_matches_from_config(repos)

    for label, comment in repo_config.items():
        if api.payload['label']['name'].lower() == label.lower():
            api.post_comment(comment)
