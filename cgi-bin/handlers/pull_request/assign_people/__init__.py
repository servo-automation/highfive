from helpers.methods import COLLABORATORS, find_reviewers


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

    if not chosen_ones:    # something's wrong?
        return

    api.set_assignees(chosen_ones)
    msgs = api.get_matches_from_config(config) or []
    if msgs:
        api.post_comment(api.rand_choice(msgs).format(reviewer=chosen_ones[0]))
