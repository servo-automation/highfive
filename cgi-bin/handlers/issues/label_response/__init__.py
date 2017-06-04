
def payload_handler(api, config):
    config = api.get_matches_from_config(config)
    if not (config and api.payload.get('action') == 'labeled'):
        return

    for label, comment in config.items():
        if api.current_label == label.lower():
            api.post_comment(comment)
