from time import sleep


def manage_pr_labels(api, config):
    repos = config.get('repos')
    action = api.payload.get('action')
    pr = api.payload.get('pull_request')
    if not (repos and pr):
        return

    is_new = action == 'opened'
    is_update = action == 'synchronize'
    is_closed = action == 'closed'
    is_mergeable = None

    if not is_closed:   # Mergeability is useful only when it's opened/updated
        is_mergeable = pr['mergeable']
        # It's a bool. If it's None, then the data isn't available yet!
        while is_mergeable is None:
            sleep(2)                    # wait for Github to determine mergeability
            pull = api.get_pull()
            is_mergeable = pull['mergeable']

    labels = api.get_matches_from_config(repos)
    labels_to_add, labels_to_remove = [], []

    if is_new or is_update:
        labels_to_add += labels['open_or_update_add']
        labels_to_remove += labels['open_or_update_remove']

        conflict_add = labels['merge_conflict_add']
        conflict_remove = labels['merge_conflict_remove']
        labels_to_add += conflict_remove if is_mergeable else conflict_add
        labels_to_remove += conflict_add if is_mergeable else conflict_remove

    elif is_closed:
        labels_to_add += labels['close_or_merge_add']
        labels_to_remove += labels['close_or_merge_remove']

    # We don't have to explicitly check whether a label exists (while removing),
    # or whether a label doesn't exist (while adding a new one)
    # APIProvider will take care of it!
    api.update_labels(labels_to_add, labels_to_remove)


methods = [manage_pr_labels]
