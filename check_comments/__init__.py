import re


def _find_reviewer(api):
    user = api.payload['comment']['user']['login']
    comment = api.payload['comment']['body']

    def get_approver():
        approval_regex = r'.*@bors-servo[: ]*r([\+=])([a-zA-Z0-9\-,]*)'
        approval = re.search(approval_regex, str(comment))

        if approval:
            if approval.group(1) == '=':    # "r=foo" or "r=foo,bar"
                reviewer = approval.group(2)
                return reviewer
            return user     # fall back and assign the approver

    reviewers = get_approver()
    if reviewers:
        api.set_assignees(reviewers.split(','))
        return

    reviewers = api.shared.find_reviewers(comment)
    if reviewers:
        api.set_assignees(reviewers)


# All these handlers are specific to Servo!
REPO_SPECIFIC_HANDLERS = {
    "servo/servo": {
        "methods": [
            _find_reviewer
        ]
    },
}


def check_comments(api, config):
    repos = config.get('repos')
    if not (api.is_open and api.payload.get('action') == 'created'):
        return

    _config = api.get_matches_from_config(repos)

    # do some stuff (if config-based handlers are added in the future)

    handlers = api.get_matches_from_config(REPO_SPECIFIC_HANDLERS)
    for method in handlers['methods']:
        method(api)


methods = [check_comments]
