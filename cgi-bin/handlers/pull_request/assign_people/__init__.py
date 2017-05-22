
def check_new_pr(api, config):
    repos = config.get('repos')
    pr = api.payload.get('pull_request')
    if not (repos and pr and api.payload.get('action') == 'opened'):
        return

    # If the PR already has an assignee, then don't try to assign one
    if pr['assignee']:
        return

    chosen_ones = api.methods.find_reviewers(pr['body'])

    if not chosen_ones:    # go for reviewer rotation
        repo_config = api.get_matches_from_config(repos)
        reviewers = filter(lambda name: name.lower() != api.creator, repo_config['assignees'])
        if not reviewers:
            return

        chosen_ones = [reviewers[int(api.issue_number) % len(reviewers)]]

    if not chosen_ones:    # something's wrong?
        return

    api.set_assignees(chosen_ones)


methods = [check_new_pr]
