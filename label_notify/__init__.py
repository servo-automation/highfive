
def notify_watchers(api, config):
    repos = config['repos']
    if not (repos and api.payload.get('action') == 'labeled'):
        return

    sender = api.payload['sender']['login'].lower()
    node = api.get_matching_path(['user', 'login'])
    creator = node['user']['login'].lower()
    new_label = api.payload['label']['name'].lower()
    watchers_to_be_notified = []

    existing_labels = filter(lambda label: label != new_label, api.get_labels())
    node = api.get_matching_path(['owner', 'login'])
    owner = node['owner']['login'].lower()
    repo = node['name'].lower()

    for name in repos:
        split = name.lower().split('/')
        if len(split) == 2:
            watcher_owner = split[0]
            # wildcard match to notify label watchers for any label event
            # triggered in a repo owned by a particular owner
            watcher_repo = repo if split[1] == '*' else split[1]
        elif split[0] == '*':
            # wildcard match to notify these users for any labels listed,
            # regardless of the owner or the repo
            watcher_owner = owner
            watcher_repo = repo
        else:
            continue        # invalid format

        if watcher_owner == owner and watcher_repo == repo:
            for user, labels in repos[name].items():
                user = user.lower()
                labels = map(lambda name: name.lower(), labels)
                # don't notify if the user's an author, or if the user is
                # the one who has triggered the label event
                if user == sender or user == creator:
                    continue

                if any(label in existing_labels for label in labels):
                    continue    # we've already notified the user

                # If we don't find any labels, then notify the user for any labelling event
                if not labels or new_label in labels:
                    watchers_to_be_notified.append(user)

    if watchers_to_be_notified:
        mentions = map(lambda name: '@%s' % name, watchers_to_be_notified)
        comment = 'cc %s' % ' '.join(mentions)
        api.post_comment(comment)


methods = [notify_watchers]
