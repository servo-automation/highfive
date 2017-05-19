from HTMLParser import HTMLParser
from datetime import datetime
from dateutil.parser import parse as datetime_parse

import json, os, re

def check_failure_log(api):
    comment = api.payload['comment']['body']
    # bors's comment would be something like,
    # ":broken_heart: Test failed - [linux2](http://build.servo.org/builders/linux2/builds/2627)"
    # ... from which we get the relevant build result url
    url = re.findall(r'.*\((.*)\)', str(comment))
    if not url:
        return

    # Substitute and get the new url
    # (e.g. http://build.servo.org/json/builders/linux2/builds/2627)
    json_url = re.sub(r'(.*)(builders/.*)', r'\1json/\2', url[0])
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
            failures = re.findall(failure_regex, stdio, re.DOTALL)

            if failures:
                failures = HTMLParser().unescape(failures[0])
                comment = [' ' * 4 + line for line in failures.split('\n')]
                comments.extend(comment)

    if comments:
        api.post_comment('\n'.join(comments))


def find_reviewer(api, data):
    comment = api.payload['comment']['body']

    def get_approver():
        approval_regex = r'.*@bors-servo[: ]*r([\+=])([a-zA-Z0-9\-,\+]*)'
        approval = re.search(approval_regex, str(comment))

        if approval:
            if approval.group(1) == '=':    # "r=foo" or "r=foo,bar"
                reviewer = approval.group(2)
                return reviewer
            return api.creator      # fall back and assign the approver

    reviewers = get_approver()
    if reviewers:
        api.set_assignees(reviewers.split(','))
        return

    reviewers = api.methods.find_reviewers(comment)
    if reviewers:
        api.set_assignees(reviewers)


def check_bors_msg(api, data):
    comment = api.payload['comment']['body']
    api.logger.debug('Checking comment by bors...')
    if 'has been approved by' in comment or 'Testing commit' in comment:
        remove_labels = ['S-awaiting-review', 'S-needs-rebase',
                         'S-tests-failed', 'S-needs-code-changes',
                         'S-needs-squash', 'S-awaiting-answer']
        api.update_labels(add=['S-awaiting-merge'], remove=remove_labels)

    elif 'Test failed' in comment:
        api.update_labels(add=['S-tests-failed'], remove=['S-awaiting-merge'])
        # Get the homu build stats url, extract the failed tests and post them!
        check_failure_log(api)

    elif 'Please resolve the merge conflicts' in comment:
        api.update_labels(add=['S-needs-rebase'], remove=['S-awaiting-merge'])

    data['labels'] = api.labels


PR_OBJ_DEFAULT = {
    'status': None,
    'body': None,
    'author': None,
    'number': None,
    'assignee': None,
    'last_active': None,
    'labels': [],
    'comments': [],
}

PR_CLOSE_MSG = ("Okay, I'm gonna close this based on inactivity. If you change your mind"
                " about working on this issue again, feel free to ping us and we'll reopen"
                " it for you. Thanks for taking a stab at this :smile:")

# FIXME: Choose randomly
PR_PING_MSG = 'Hey @%s! Are you planning to finish this off?'

MAX_DAYS = 4


def check_pulls(api, dump_path):
    for number in os.listdir(dump_path):        # Check existing PRs
        pr_path = os.path.join(dump_path, number)
        with open(pr_path, 'r') as fd:
            api.logger.debug('Checking data for PR #%s...', number)
            data = json.load(fd)

        if data.get('owner') and data.get('repo'):
            api.owner, api.repo = data['owner'], data['repo']
        else:   # We pass a fake payload here (so, owner and repo should be valid to proceed)
            api.logger.debug('No info about owner and repo in JSON. Skipping this cycle...')
            continue

        last_active = data['last_active']
        if not last_active:
            continue

        last_active = datetime_parse(last_active)
        now = datetime.now(last_active.tzinfo)
        if (now - last_active).days <= MAX_DAYS:
            api.logger.debug('PR #%s is stil in grace period', number)
            continue

        api.logger.debug("PR #%s has had its time. Something's gonna happen.", number)
        api.issue_number = number
        data['last_active'] = str(now)
        assignee = data['assignee']
        status = data['status']

        if status is None:
            api.post_comment(PR_PING_MSG % assignee)
            data['status'] = 'commented'
        elif status == 'commented':
            api.logger.debug('Closing PR #%s after grace period', pr_num)
            api.post_comment(PR_CLOSE_MSG)
            api.close_issue()
            continue

        with open(pr_path, 'w') as fd:
            json.dump(data, fd)


def manage_pulls(api, dump_path):
    payload = api.payload
    action = payload.get('action')
    if action is None:
        check_pulls(api, dump_path)
        return

    if not (api.is_open and payload.get('pull_request')):
        return

    if not os.path.isdir(dump_path):
        os.mkdir(dump_path)

    data = PR_OBJ_DEFAULT
    pr_path = os.path.join(dump_path, str(api.issue_number))
    if os.path.exists(pr_path):
        api.logger.debug('Loading JSON from %r', pr_path)
        with open(pr_path, 'r') as fd:
            data = json.load(fd)

    if data.get('owner') is None and api.owner:
        data['owner'] = api.owner
    if data.get('repo') is None and api.repo:
        data['repo'] = api.repo

    if action == 'created':                 # comment
        find_reviewer(data, api)
        if api.creator == 'bors-servo':
            check_bors_msg(data, api)
        data['last_active'] = payload['comment']['updated_at']
        data['comments'].append(payload['comment']['body'])
        data['labels'] = api.labels
    elif action == 'opened':                # PR created
        data['author'] = api.creator
        data['number'] = api.issue_number
        data['labels'] = api.labels
        data['last_active'] = payload['pull_request']['updated_at']
        data['body'] = payload['pull_request']['body']
        data['assignee'] = payload['pull_request']['assignee']
        data['last_active'] = payload['pull_request']['updated_at']
    elif action == 'labeled':
        data['labels'] = list(set(data['labels']).union([payload['label']['name']]))
    elif action == 'unlabeled':
        data['labels'] = list(set(data['labels']).difference([payload['label']['name']]))
    elif action == 'closed' and os.path.exists(pr_path):
        api.logger.debug('PR #%s closed. Removing JSON...', api.issue_number)
        os.remove(pr_path)
        return
    # FIXME: Maybe check commit event, pull changes, run stuff locally and post comments
    # (test-tidy for example)

    with open(pr_path, 'w') as fd:
        api.logger.debug('Dumping JSON to %r', pr_path)
        json.dump(data, fd)


REPO_SPECIFIC_HANDLERS = {
    "servo/servo": manage_pulls
}

def pr_manager(api, _config, data):
    handler = api.get_matches_from_config(REPO_SPECIFIC_HANDLERS)
    if handler:
        handler(api, data)


methods = [pr_manager]
