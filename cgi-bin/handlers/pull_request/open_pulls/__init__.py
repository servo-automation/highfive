from HTMLParser import HTMLParser
from copy import deepcopy
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
PR_ANON_PING = "What's going on here?"

MAX_DAYS = 4


def check_pulls(api, db, inst_id, self_name):
    for number in db.get_obj(inst_id, self_name):       # Check existing PRs
        data = db.get_obj(inst_id, '%s_%s' % (self_name, number))
        old_data = deepcopy(data)

        if data.get('owner') and data.get('repo'):
            api.owner, api.repo = data['owner'], data['repo']
        else:   # We pass a fake payload here (so, owner and repo should be valid to proceed)
            api.logger.debug('No info about owner and repo in JSON. Skipping this cycle...')
            continue

        last_active = data.get('last_active')
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
        status = data.get('status')

        if status is None:
            api.post_comment(PR_PING_MSG % data['author'])
            data['status'] = 'commented'
        elif status == 'commented':
            api.logger.debug('Closing PR #%s after grace period', number)
            api.post_comment(PR_CLOSE_MSG)
            api.close_issue()
            continue

        if data != old_data:
            db.write_obj(data, inst_id, '%s_%s' % (self_name, number))


def manage_pulls(api, db, inst_id, self_name):
    payload = api.payload
    action = payload.get('action')
    if action is None:
        return check_pulls(api, db, inst_id, self_name)

    pr_list = db.get_obj(inst_id, self_name) or []
    old_list = deepcopy(pr_list)
    if not (api.is_open and (api.issue_number in pr_list or api.is_pull)):
        return      # Note that issue_comment event will never have "pull_request"

    data = db.get_obj(inst_id, '%s_%s' % (self_name, api.issue_number)) or PR_OBJ_DEFAULT
    remove_data = False
    old_data = deepcopy(data)
    if api.issue_number not in pr_list:
        pr_list.append(api.issue_number)

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
    elif action == 'opened':                # PR created
        data['author'] = api.creator
        data['number'] = api.issue_number
        data['labels'] = api.labels
        data['body'] = payload['pull_request']['body']
        data['assignee'] = payload['pull_request']['assignee']
        data['last_active'] = payload['pull_request']['updated_at']
    elif action == 'labeled':
        data['labels'] = list(set(data['labels']).union([payload['label']['name']]))
        data['last_active'] = payload['pull_request']['updated_at']
    elif action == 'unlabeled':
        data['labels'] = list(set(data['labels']).difference([payload['label']['name']]))
        data['last_active'] = payload['pull_request']['updated_at']
    elif action == 'closed':
        api.logger.debug('PR #%s closed. Removing JSON...', api.issue_number)
        pr_list.remove(api.issue_number)
        remove_data = True
    # FIXME: Maybe check commit event, pull changes, run stuff locally and post comments
    # (test-tidy for example)

    if remove_data:
        db.remove_obj(inst_id, '%s_%s' % (self_name, api.issue_number))
    elif data != old_data:
        db.write_obj(data, inst_id, '%s_%s' % (self_name, api.issue_number))

    if pr_list != old_list:
        db.write_obj(pr_list, inst_id, self_name)


REPO_SPECIFIC_HANDLERS = {
    "servo/servo": manage_pulls
}

def pr_manager(api, _config, data):
    handler = api.get_matches_from_config(REPO_SPECIFIC_HANDLERS)
    if handler:
        handler(api, data)


methods = [pr_manager]
