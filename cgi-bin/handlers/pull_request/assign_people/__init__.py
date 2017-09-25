from helpers.methods import COLLABORATORS, find_reviewers, join_names


def payload_handler(api, config):
    reviewers = api.get_matches_from_config(COLLABORATORS)
    if not (reviewers and api.is_pull and api.payload.get('action') == 'opened'):
        return

    # If the PR already has an assignee, then don't try to assign one
    if api.payload['pull_request']['assignee']:
        return

    chosen_ones = find_reviewers(api.payload['pull_request']['body'])

    if not chosen_ones:    # go for reviewer rotation
        reviewers = filter(lambda name: name.lower() != api.creator, reviewers)
        if not reviewers:
            return

        chosen_ones = [reviewers[int(api.issue_number) % len(reviewers)]]

    api.set_assignees(chosen_ones)
    match = api.get_matches_from_config(config)
    if not match:
        return

    first = [chosen_ones[0]]
    rest = map(lambda s: '@' + s, chosen_ones[1:])
    mention = join_names(first + rest)
    api.post_comment(api.rand_choice(match['reviewer_msg']).format(reviewer=mention))

    foss_folks = api.get_contributors()
    if api.creator not in foss_folks:
        msg = api.rand_choice(match['newcomer_welcome_msg']).format(reviewer=mention)
        api.post_comment(msg)
