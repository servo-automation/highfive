
def notify_watchers(api, config):
    repos = config['repos']
    if not repos:
        return

    sender = api.payload['sender']['login'].lower()
    node = api.get_matching_path(['user', 'login'])
    creator = node['user']['login'].lower()
    new_label = api.payload['label']['name']
    watchers_to_be_notified = []

    node = api.get_matching_path(['owner', 'login'])
    owner = node['owner']['login']
    repo = node['name']

    # FIXME: It turns out that adding multiple labels at the same time sends
    # payloads containing individual labels (instead of sending them as a list).
    # So, we won't probably know whether we've notified someone earlier. This
    # results in the risk of multiple notifications for the same user. In order
    # to get around this, maybe we should make an API request getting the initial
    # list of labels and filter the users (if the label already exists)

    for name in repos:
        split = name.split('/')
        if len(split) == 2:
            watcher_owner = split[0]
            # wildcard match to notify label watchers for any label event
            # triggered in a repo owned by a particular owner
            watcher_repo = repo if split[1] == '*' else split[1]
        elif split[0] == '*'
            # notify these users for any labels listed, regardless of
            # the owner or the repo
            watcher_owner = owner
            watcher_repo = repo

        if watcher_owner == owner and watcher_repo == repo:
            for user, labels in repos[name].items():
                # don't notify if the user's an author, or if the user is
                # the one who has triggered the label event
                if user == sender or user == creator:
                    continue

                if new_label in labels:
                    watchers_to_be_notified.append(user)

        if watchers_to_be_notified:
            mentions = map(lambda name: '@%s' % name, watchers_to_be_notified)
            comment = 'cc %s' % ' '.join(mentions)
            api.post_comment(comment)


methods = [notify_watchers]
