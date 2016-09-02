from time import sleep


def manage_pr_labels(api, config):
    repos = config.get(repos)
    action = api.payload.get('action')
    pr = api.payload.get('pull_request')
    if not (repos and pr):
        return

    is_new = action == 'opened'
    is_update = action == 'synchronize'
    is_closed = action == 'closed'
    is_mergeable = pr['mergeable']  # It's a bool. If it's None, then the data isn't available yet!

    while is_mergeable is None:
        sleep(2)                    # wait for Github to determine mergeability
        pull = api.get_pull()
        is_mergeable = pull['mergeable']

    # ideally, this should iterate only once (assuming the config is valid)
    for name in api.get_matching_repos(repos):
        labels = config[name]
        labels_to_add = labels['merge_conflict_add'] if is_mergeable else labels['merge_conflict_remove']
        labels_to_remove = labels['merge_conflict_remove'] if is_mergeable else labels['merge_conflict_add']

        if is_new or is_update:
            labels_to_add += labels['open_or_update_add']
            labels_to_remove += labels['open_or_update_remove']
        elif is_closed:
            labels_to_add += labels['close_or_merge_add']
            labels_to_remove += labels['close_or_merge_remove']

        api.update_labels(labels_to_add, labels_to_remove)


methods = [manage_pr_labels]
