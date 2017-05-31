
def payload_handler(api, config):
    repos = config.get('repos')
    if not (repos and api.payload.get('action') == 'labeled'):
        return

    watchers_to_be_notified = []

    new_label = api.payload['label']['name'].lower()
    existing_labels = set(api.labels) - set([new_label])
    repo_config = api.get_matches_from_config(repos)

    for user, labels in repo_config.items():
        user = user.lower()
        labels = map(lambda name: name.lower(), labels)
        # don't notify if the user's an author, or if the user is
        # the one who has triggered the label event
        if user == api.sender or user == api.creator:
            continue

        if any(label in existing_labels for label in labels):
            continue    # we've already notified the user

        # If we don't find any labels, then notify the user for any labelling event
        if (api.labels and not labels) or new_label in labels:
            watchers_to_be_notified.append(user)

    if watchers_to_be_notified:
        mentions = map(lambda name: '@%s' % name, watchers_to_be_notified)
        comment = 'cc %s' % ' '.join(mentions)
        api.post_comment(comment)
