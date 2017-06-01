
def payload_handler(api, config):
    config = api.get_matches_from_config(config)
    if not (config and api.is_pull and api.payload.get('action') == 'opened'):
        return

    mentions = {}
    for path in api.get_changed_files():
        for user, watched in config.items():
            if user == api.creator:     # don't mention the creator
                continue

            not_watched = filter(lambda p: p.startswith('-'), watched)
            not_watched = map(lambda p: p.lstrip('-'), not_watched)
            watched = filter(lambda p: not p.startswith('-'), watched)

            for watched_path in watched:
                if path.startswith(watched_path):
                    if any(path.startswith(p) for p in not_watched):
                        continue

                    mentions.setdefault(user, [])
                    mentions[user].append(path)

    if not mentions:
        return

    message = ['Heads up! This PR modifies the following files:']
    for watcher, files in mentions.items():
        message.append(" * @{}: {}".format(watcher, ', '.join(files)))

    api.post_comment('\n'.join(message))
