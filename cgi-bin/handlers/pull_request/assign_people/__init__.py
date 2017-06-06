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
    msgs = api.get_matches_from_config(config) or []
    if msgs:
        first = [chosen_ones[0]]
        rest = map(lambda s: '@' + s, chosen_ones[1:])
        api.post_comment(api.rand_choice(msgs).format(reviewer=join_names(first + rest)))
