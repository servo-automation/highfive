from time import sleep


def payload_handler(api, config):
    labels = api.get_matches_from_config(config)
    if not (labels and api.is_pull):
        return

    action = api.payload.get('action')
    is_new = action == 'opened'
    is_update = action == 'synchronize'
    is_closed = action == 'closed'
    is_mergeable = None
    labels_to_add, labels_to_remove = [], []

    if not is_closed:   # Mergeability is useful only when it's opened/updated
        is_mergeable = api.payload['pull_request']['mergeable']
        # It's a bool. If it's None, then the data isn't available yet!
        while is_mergeable is None:
            sleep(2)                    # wait for Github to determine mergeability
            pull = api.get_pull()
            is_mergeable = pull['mergeable']

    if is_new or is_update:
        labels_to_add += labels.get('open_or_update_add', [])
        labels_to_remove += labels.get('open_or_update_remove', [])

        conflict_add = labels.get('merge_conflict_add', [])
        conflict_remove = labels.get('merge_conflict_remove', [])
        labels_to_add += conflict_remove if is_mergeable else conflict_add
        labels_to_remove += conflict_add if is_mergeable else conflict_remove

    elif is_closed:
        labels_to_add += labels.get('close_or_merge_add', [])
        labels_to_remove += labels.get('close_or_merge_remove', [])

    # We don't have to explicitly check whether a label exists (while removing),
    # or whether a label doesn't exist (while adding a new one)
    # APIProvider will take care of it!
    api.update_labels(labels_to_add, labels_to_remove)
