
def check_new_pr(api, config):
    repos = config.get('repos')
    pr = api.payload.get('pull_request')
    if not (repos and pr and api.payload.get('action') == 'opened'):
        return

    # If the PR already has an assignee, then don't try to assign one
    if pr['assignee'] != None:
        return

    reviewer = api.shared.find_reviewers(pr['body'])

    if not reviewer:    # go for reviewer rotation
        for config in api.get_matches_from_config(repos):
            _sender, creator = api.get_sender_and_creator()     # both are same in this case
            reviewers = filter(lambda name: name.lower() != creator.lower(), config['assignees'])
            reviewer = reviewers[pr['number'] % len(reviewers)]

    if not reviewer:    # something's wrong?
        return

    api.set_assignees(reviewer)


methods = [check_new_pr]
