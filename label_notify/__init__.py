
def notify_watchers(api, config):
    repos = config.get('repos')
    if not (repos and api.payload.get('action') == 'labeled'):
        return

    watchers_to_be_notified = []
    sender, creator = api.get_sender_and_creator()

    existing_labels = filter(lambda label: label != new_label, api.get_labels())
    new_label = api.payload['label']['name'].lower()

    for config in api.get_matches_from_config(repos):
        for user, labels in config.items():
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
