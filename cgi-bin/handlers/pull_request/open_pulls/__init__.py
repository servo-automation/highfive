from HTMLParser import HTMLParser
from copy import deepcopy
from datetime import datetime
from dateutil.parser import parse as datetime_parse

from helpers.methods import COLLABORATORS, find_reviewers

import json, os, re

def default():
    return {
        'status': None,         # None or 'commented'
        'body': None,
        'author': None,
        'number': None,
        'assignee': None,
        'last_active': None,
        'last_push': None,
        'labels': [],
        'comments': [],
    }


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
    failure_regex = r'Tests with unexpected results:\n(.*)\n</span><span'
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


def assign_reviewer(api):
    if api.payload.get('action') != 'created':
        return

    comment = api.payload['comment']['body']

    def get_approver():
        approval_regex = r'.*@bors-servo[: ]*r([\+=])([a-zA-Z0-9\-,\+]*)'
        approval = re.search(approval_regex, str(comment))

        if approval:
            if approval.group(1) == '=':    # "r=foo" or "r=foo,bar"
                reviewer = approval.group(2)
                return reviewer
            return api.sender       # fall back and assign the approver

    reviewers = get_approver()
    if reviewers:
        api.set_assignees(reviewers.split(','))
        return

    reviewers = find_reviewers(comment)
    if reviewers:
        api.set_assignees(reviewers)


def check_bors_msg(api):
    if api.sender != 'bors-servo' or api.payload.get('action') != 'created':
        return

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


def check_pulls(api, config, db, inst_id, self_name):
    for number in db.get_obj(inst_id, self_name):       # Check existing PRs
        data = db.get_obj(inst_id, '%s_%s' % (self_name, number))
        old_data = deepcopy(data)

        if data.get('owner') and data.get('repo'):
            api.owner, api.repo = data['owner'], data['repo']
        else:   # We pass a fake payload here (so, owner and repo should be valid to proceed)
            api.logger.debug('No info about owner and repo in JSON. Skipping this cycle...')
            continue

        config = api.get_matches_from_config(config)
        last_active = data.get('last_active')
        if not last_active:
            continue

        last_active = datetime_parse(last_active)
        now = datetime.now(last_active.tzinfo)
        if (now - last_active).days <= config['grace_period_days']:
            api.logger.debug('PR #%s is stil in grace period', number)
            continue

        api.logger.debug("PR #%s has had its time. Something's gonna happen.", number)
        api.issue_number = number
        data['last_active'] = str(now)
        status = data.get('status')

        if not data['assignee']:    # assign someone randomly if we don't find an assignee after grace period
            reviewers = filter(lambda name: name.lower() != data['author'],
                               api.get_matches_from_config(COLLABORATORS))
            new_assignee = api.rand_choice(reviewers)
            api.set_assignees([new_assignee])
            comment = api.rand_choice(config['review_ping'])
            api.post_comment(comment.format(reviewer=new_assignee))
            continue    # skip this cycle

        if status is None:
            should_ping_reviewer = False
            assignee_comments = filter(lambda d: d['who'] == data['assignee'], data['comments'])
            author_comments = filter(lambda d: d['who'] == data['author'], data['comments'])
            if not assignee_comments:
                should_ping_reviewer = True     # reviewer hasn't commented at all!
            elif not author_comments:
                last_review = datetime_parse(assignee_comments[-1]['when'])
                last_push = datetime_parse(data['last_push'])
                if last_review < last_push:         # reviewer hasn't looked at this since the last push
                    should_ping_reviewer = True
                else:
                    comment = api.rand_choice(config['pr_ping'])
                    api.post_comment(comment.format(author=data['author']))
                    data['status'] = 'commented'
            else:
                # It could be waiting on the assignee or the author. Right now, we just poke them both.
                api.post_comment(api.rand_choice(config['pr_anon_ping']))

            if should_ping_reviewer:
                # Right now, we just ping the reviewer until he takes a look at this or assigns someone else
                comment = api.rand_choice(config['review_ping'])
                api.post_comment(comment.format(reviewer=data['assignee']))

        elif status == 'commented':
            api.logger.debug('Closing PR #%s after grace period', number)
            comment = api.rand_choice(config['pr_close'])
            api.post_comment(comment.format(author=data['author']))
            api.close_issue()
            continue

        if data != old_data:
            db.write_obj(data, inst_id, '%s_%s' % (self_name, number))


def manage_pulls(api, config, db, inst_id, self_name):
    payload = api.payload
    action = payload.get('action')
    if action is None:
        return check_pulls(api, config, db, inst_id, self_name)

    pr_list = db.get_obj(inst_id, self_name) or []
    old_list = deepcopy(pr_list)
    # Note that issue_comment event will never have "pull_request" even if the comment
    # is dropped in a PR. So, we can't check for pull_request here.

    data = db.get_obj(inst_id, '%s_%s' % (self_name, api.issue_number)) or default()

    remove_data = False
    old_data = deepcopy(data)
    is_pr_in_list = api.issue_number in pr_list

    if data.get('owner') is None and api.owner:
        data['owner'] = api.owner
    if data.get('repo') is None and api.repo:
        data['repo'] = api.repo

    if is_pr_in_list:
        if action == 'created':
            data['last_active'] = api.last_updated
            comment = payload['comment']['body']
            data['status'] = None
            data['comments'].append({
                'body': comment,
                'when': api.last_updated,
                'who': api.sender
            })
        elif action == 'synchronize':
            data['last_push'] = data['last_active'] = api.last_updated
            data['status'] = None
        elif action == 'assigned' or action == 'unassigned':
            data['assignee'] = api.assignee
            data['last_active'] = api.last_updated
        elif action == 'labeled':
            data['labels'] = list(set(data['labels']).union([api.current_label]))
            # data['last_active'] = api.last_updated
        elif action == 'unlabeled':
            data['labels'] = list(set(data['labels']).difference([api.current_label]))
            # data['last_active'] = api.last_updated
        elif action == 'closed':
            api.logger.debug('PR #%s closed. Removing JSON...', api.issue_number)
            pr_list.remove(api.issue_number)
            remove_data = True
    elif api.is_pull and (action == 'opened' or action == 'reopened'):
        pr_list.append(api.issue_number)
        data['author'] = api.creator
        data['number'] = api.issue_number
        data['labels'] = api.labels
        data['body'] = payload['pull_request']['body']
        data['assignee'] = api.assignee
        data['last_push'] = data['last_active'] = api.last_updated

    if pr_list != old_list:
        db.write_obj(pr_list, inst_id, self_name)
        if remove_data:
            db.remove_obj(inst_id, '%s_%s' % (self_name, api.issue_number))
        elif data != old_data:
            db.write_obj(data, inst_id, '%s_%s' % (self_name, api.issue_number))


REPO_SPECIFIC_HANDLERS = {
    'servo/': [
        assign_reviewer,
    ],
    'servo/servo': [
        check_bors_msg,
    ],
}


def payload_handler(api, config, db, inst_id, name):
    config = api.get_matches_from_config(config)
    if config:
        manage_pulls(api, config, db, inst_id, name)

    if not api.payload:     # happens when we poke the handler states
        return

    other_handlers = api.get_matches_from_config(REPO_SPECIFIC_HANDLERS) or []
    for handler in other_handlers:
        handler(api)
