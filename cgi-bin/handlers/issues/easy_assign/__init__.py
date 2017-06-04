from copy import deepcopy
from datetime import datetime
from dateutil.parser import parse as datetime_parse

from helpers.methods import COLLABORATORS

import json, os, re

def default():      # create a new value every call, so that the values don't get overridden
    return {
        'assignee': None,
        'status': None,             # None, 'assigned', 'pull', 'commented'
        'last_active': None,
        'pr_number': None,
    }

def check_easy_issues(api, config, db, inst_id, self_name):
    payload = api.payload
    action = payload.get('action')
    data = db.get_obj(inst_id, self_name)
    old_data = deepcopy(data)

    if data.get('issues') is None:
        data['issues'] = {}
    if data.get('owner') is None and api.owner:
        data['owner'] = api.owner
    if data.get('repo') is None and api.repo:
        data['repo'] = api.repo

    is_issue_in_data = data['issues'].has_key(api.issue_number) if api.issue_number else None
    reviewers = api.get_matches_from_config(COLLABORATORS) or []

    if action == 'opened' or action == 'reopened':          # issue or PR
        if api.is_pull:
            pr_body = payload['pull_request']['body']
            # check whether the PR addresses an issue in our store
            match = re.search(r'(?:fixe?|close|resolve)[s|d]? #([0-9]*)', str(pr_body))
            number = match.group(1) if match else None
            if number and data['issues'].has_key(number):
                api.logger.debug('PR #%s addresses issue #%s', api.issue_number, number)
                assignee = data['issues'][number]['assignee']
                if assignee == '0xdeadbeef':        # Assume that this author is the anonymous assignee
                    assignee = api.creator

                data['issues'][number]['assignee'] = api.creator
                data['issues'][number]['pr_number'] = api.issue_number
                data['issues'][number]['status'] = 'pull'
                data['issues'][number]['last_active'] = payload['pull_request']['updated_at']

                if assignee is None:        # PR author hasn't claimed the issue
                    api.logger.debug('Assignee has not requested issue assignment.'
                                     ' Marking issue as assigned')
                    api.post_comment(api.rand_choice(config['dup_effort']))
                    api.issue_number = number
                    api.update_labels(add=[config['assign_label']])

                elif api.creator != assignee:       # PR author isn't the assignee
                    api.logger.debug('Assignee collision: Expected %r but PR author is %r',
                                     assignee, api.creator)
                    # Currently, we just drop a notification in the PR
                    comment = api.rand_choice(config['possible_dup'])
                    api.post_comment(comment.format(issue=number))
        elif config['easy_label'] in api.labels:        # it's an issue and contains appropriate labels
            if config['assign_label'] in api.labels:
                api.logger.debug('Issue #%s has been assigned to someone (while opening)', api.issue_number)
                data['issues'][api.issue_number] = default()
                data['issues'][api.issue_number]['assignee'] = '0xdeadbeef'
                data['issues'][api.issue_number]['status'] = 'assigned'
                data['issues'][api.issue_number]['last_active'] = payload['issue']['updated_at']
            else:
                api.logger.debug('Issue #%s has been marked as easy (while opening). Posting welcome comment...',
                                 api.issue_number)
                data['issues'][api.issue_number] = default()

    elif action == 'created' and not api.is_pull and not api.is_from_self():
        msg = payload['comment']['body']
        match = re.search(r'@%s(?:\[bot\])?[: ]*assign @?(.*)' % api.name, str(msg.lower()))
        if match:
            name = match.group(1).split(' ')[0]
            if name == 'me':
                if config['assign_label'] in api.labels:
                    if not is_issue_in_data:
                        data['issues'][api.issue_number] = default()
                        data['issues'][api.issue_number]['assignee'] = '0xdeadbeef'

                    data['issues'][api.issue_number]['status'] = 'assigned'
                    data['issues'][api.issue_number]['last_active'] = payload['comment']['updated_at']

                    api.logger.debug('Assignee collision. Leaving it to core contributor...')
                    api.post_comment(api.rand_choice(config['assign_fail']))
                else:
                    # This way, assigning applies to "any" issue. If it's assigned, then
                    # highfive will start tracking those issues and the associating PRs.
                    if not is_issue_in_data:
                        data['issues'][api.issue_number] = default()

                    api.logger.debug('Got assign request. Assigning to %r', api.creator)
                    api.update_labels(add=[config['assign_label']])
                    comment = api.rand_choice(config['assign_success'])
                    api.post_comment(comment.format(assignee=api.creator))

                    data['issues'][api.issue_number]['assignee'] = api.creator
                    data['issues'][api.issue_number]['status'] = 'assigned'
                    data['issues'][api.issue_number]['last_active'] = payload['comment']['updated_at']
            else:
                if api.sender in reviewers:
                    api.logger.debug('Got assign request from reviewer. Assigning to %r', name)
                    data['issues'][api.issue_number] = default()
                    data['issues'][api.issue_number]['assignee'] = name
                    data['issues'][api.issue_number]['status'] = 'assigned'
                    data['issues'][api.issue_number]['last_active'] = payload['comment']['updated_at']
                    api.update_labels(add=[config['assign_label']])
                    api.post_comment(api.rand_choice(config['assign_success']).format(assignee=name))
                else:
                    api.post_comment(api.rand_choice(config['non_reviewer_ack']))
        elif is_issue_in_data:
            # FIXME: Someone has commented in the issue. Multiple things to investigate.
            # What if the assignee had asked some question and no one answered?
            # What if the issue gets blocked on something else?
            # For now, we assume that our reviewers don't leave an easy issue unnoticed for 4 days!
            # Maybe we could have another handler for pinging the reviewer if a question
            # remains unanswered for a while.
            data['issues'][api.issue_number]['last_active'] = payload['comment']['updated_at']
            if data['issues'][api.issue_number]['status'] == 'commented' and not api.is_from_self():
                data['issues'][api.issue_number]['status'] = 'assigned'

    elif action == 'closed':
        num = api.issue_number
        if is_issue_in_data:
            api.logger.debug('Issue #%s is being closed. Removing related data...', num)
            data['issues'].pop(num)
        elif (api.is_pull and any(i['pr_number'] == num for i in data['issues'].itervalues())):
            issue_num = filter(lambda i: data['issues'][i]['pr_number'] == num, data['issues'])[0]
            if api.sender == api.creator:
                api.logger.debug('PR #%s is being closed by its author. Keeping issue assigned...')
                data['issues'][issue_num]['status'] = 'assigned'
                data['issues'][issue_num]['last_active'] = payload['pull_request']['updated_at']
                data['issues'][issue_num]['pr_number'] = None
            else:
                api.logger.debug('PR #%s has been closed by a collaborator. Removing related data...', num)
                comment = api.rand_choice(config['previous_work']) + ' ' + api.rand_choice(config['issue_unassign'])
                api.issue_number = issue_num
                api.post_comment(comment.format(author=api.creator, pull=num))
                api.update_labels(remove=[config['assign_label']])
                data['issues'][issue_num] = default()

    elif action == 'labeled' and api.is_open and not api.is_pull:
        if api.current_label == config['easy_label'] and not is_issue_in_data:
            # NOTE: We also make sure that the issue isn't in our data (since we do the
            # same thing when an issue is opened with an easy label)
            api.logger.debug('Issue #%s has been marked E-easy. Posting welcome comment...',
                              api.issue_number)
            data['issues'][api.issue_number] = default()
            comment = api.rand_choice(config['issue_assign'])
            api.post_comment(comment.format(bot=api.name))
        elif (api.current_label == config['assign_label'] and not api.is_from_self()):
            api.logger.debug('Issue #%s has been assigned to... someone?', api.issue_number)
            # We always override here, because labels can be added only by collaborators and
            # so, their decision is final.
            if not is_issue_in_data:
                data['issues'][api.issue_number] = default()

            data['issues'][api.issue_number]['assignee'] = '0xdeadbeef'
            data['issues'][api.issue_number]['status'] = 'assigned'
            data['issues'][api.issue_number]['last_active'] = payload['issue']['updated_at']

    elif (action == 'unlabeled' and not api.is_pull):
        if api.current_label == config['easy_label'] and is_issue_in_data:
            api.logger.debug('Issue #%s is no longer E-easy. Removing related data...',
                             api.issue_number)
            data['issues'].pop(api.issue_number)
        elif api.current_label == config['assign_label']:
            api.logger.debug('Issue #%s has been unassigned. Setting issue to default data...',
                             api.issue_number)
            data['issues'][api.issue_number] = default()

    elif action is None:    # check the timestamps and post comments as necessary
        if data.get('owner') and data.get('repo'):
            api.owner, api.repo = data['owner'], data['repo']
        else:   # We pass a fake payload here (so, owner and repo should be valid to proceed)
            api.logger.debug('No info about owner and repo in JSON. Skipping this cycle...')
            return

        config = api.get_matches_from_config(config)
        # Note that the `api` variable beyond this point shouldn't be trusted for
        # anything more than the names of owner, repo, its methods and its logger.
        # All other variables are invalid.
        for number, issue in data['issues'].iteritems():
            status = issue['status']
            last_active = issue['last_active']
            if not last_active:
                continue

            last_active = datetime_parse(last_active)
            now = datetime.now(last_active.tzinfo)
            if (now - last_active).days <= config['grace_period_days']:
                api.logger.debug('Issue #%s is stil in grace period', number)
                continue
            elif status == 'pull':          # PR handler will take care
                continue

            api.logger.debug("Issue #%s has had its time. Something's gonna happen.", number)
            api.issue_number = number
            assignee = issue['assignee']
            data['issues'][number]['last_active'] = str(now)

            if status == 'assigned':
                api.logger.debug('Pinging %r in issue #%s', assignee, number)
                if assignee == '0xdeadbeef':
                    api.post_comment(api.rand_choice(config['unknown_ping']))
                else:
                    api.post_comment(api.rand_choice(config['known_ping']).format(assignee=assignee))
                data['issues'][number]['status'] = 'commented'
            elif status == 'commented':
                api.logger.debug('Unassigning issue #%s after grace period', number)
                api.update_labels(remove=[config['assign_label']])
                api.post_comment(api.rand_choice(config['issue_unassign']))      # another payload will reset the data

    if data != old_data:
        db.write_obj(data, inst_id, self_name)


def payload_handler(api, config, db, inst_id, name):
    config = api.get_matches_from_config(config)
    if config:
        check_easy_issues(api, config, db, inst_id, name)
