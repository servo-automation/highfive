from HTMLParser import HTMLParser

import json, re


def check_failure_log(api, comment):
    # bors's comment would be something like,
    # ":broken_heart: Test failed - [linux2](http://build.servo.org/builders/linux2/builds/2627)"
    # ... from which we get the relevant build result url
    url = iter(re.findall(r'.*\((.*)\)', str(comment))).next()
    if not url:
        return

    # Substitute and get the new url
    # (e.g. http://build.servo.org/json/builders/linux2/builds/2627)
    json_url = re.sub(r'(.*)(builders/.*)', r'\1json/\2', url)
    json_stuff = api.get_page_content(json_url)
    if not json_stuff:
        return

    build_stats = json.loads(json_stuff)
    failure_regex = r'.*Tests with unexpected results:\n(.*)\n</span><span'
    comments = []

    for step in build_stats['steps']:
        if 'failed' not in step['text']:
            continue

        for name, log_url in step['logs']:
            if name != 'stdio':
                continue

            stdio = api.get_page_content(log_url)
            failures = iter(re.findall(failure_regex, stdio, re.DOTALL)).next()
            failures = HTMLParser().unescape(failures)

            if failures:
                comment = [' ' * 4 + line for line in failures.split('\n')]
                comments.extend(comment)

    if comments:
        api.post_comment('\n'.join(comments))


def _find_reviewer(api):
    user = api.payload['comment']['user']['login']
    comment = api.payload['comment']['body']

    def get_approver():
        approval_regex = r'.*@bors-servo[: ]*r([\+=])([a-zA-Z0-9\-,\+]*)'
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


def _watch_bors(api):
    user = api.payload['comment']['user']['login']
    comment = api.payload['comment']['body']

    if user != 'bors-servo':
        return

    if 'has been approved by' in comment or 'Testing commit' in comment:
        remove_labels = ['S-awaiting-review', 'S-needs-rebase',
                         'S-tests-failed', 'S-needs-code-changes',
                         'S-needs-squash', 'S-awaiting-answer']
        api.update_labels(add=['S-awaiting-merge'], remove=remove_labels)

    elif 'Test failed' in comment:
        api.update_labels(add=['S-tests-failed'], remove=['S-awaiting-merge'])
        # Get the homu build stats url,
        # extract the failed tests and post them!
        check_failure_log(api, comment)

    elif 'Please resolve the merge conflicts' in comment:
        api.update_labels(add=['S-needs-rebase'], remove=['S-awaiting-merge'])


# All these handlers are specific to Servo!
REPO_SPECIFIC_HANDLERS = {
    "servo/servo": {
        "methods": [
            _find_reviewer,
            _watch_bors,
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
    for method in handlers.get('methods', []):
        method(api)


methods = [check_comments]
