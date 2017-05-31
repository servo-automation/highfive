from copy import deepcopy
from datetime import datetime
from dateutil.parser import parse as datetime_parse

import json, os, re

ASSIGN_MSG = ('Hi! If you have any questions regarding this issue, feel free to make'
              ' a comment here, or ask it in the `#servo` channel in '
              '[IRC](https://wiki.mozilla.org/IRC).\n\n'
              'If you intend to work on this issue, then add `@%s: assign me`'
              ' to your comment, and I\'ll assign this to you. :smile:')

DUP_EFFORT_MSG = ('Hello there! Thanks for picking up this issue! We really appreciate your effort.'
                  ' But, in the future, please get the issue assigned to yourself before working'
                  ' on it, so that we can avoid duplicate efforts. :smile:')

POSSIBLE_DUP = ("Hmm, it appears to me that the author of this pull request"
                " isn't the one who claimed #%s :thinking:")

RESPONSE_FAIL = ('It looks like this has already been assigned to someone.'
                 ' I\'ll leave the decision to a core contributor.')

RESPONSE_OK = ('Hey @%s! Thanks for your interest in working on this issue.'
               ' It\'s now assigned to you!')

PR_ADDRESS_MSG = 'Previous work on #%s. '
ISSUE_UNASSIGN_MSG = 'This is now open for anyone to jump in!'

# FIXME: These responses may occur often, and should probably have a list of messages
# to be chosen at random
ISSUE_PING_MSG = 'Ping @%s! Did you look into this? You got any questions for us?'
ISSUE_ANON_PING = 'Is this still being worked on?'

ISSUE_OBJ_DEFAULT = {
    'assignee': None,
    'status': None,             # None, 'assigned', 'pull', 'commented'
    'last_active': None,
    'pr_number': None,
}

MAX_DAYS = 4


def check_easy_issues(api, db, inst_id, self_name):
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

    if action == 'opened':                  # issue or PR
        if payload.get('pull_request'):
            pr_body = payload['pull_request']['body']
            # check whether the PR addresses an issue in our store
            match = re.search(r'(?:fixe?|close|resolve)[s|d]? #([0-9]*)', pr_body)
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
                    api.post_comment(DUP_EFFORT_MSG)
                    api.issue_number = number
                    api.update_labels(add=['C-assigned'])

                if api.creator != assignee:     # PR author isn't the assignee
                    api.logger.debug('Assignee collision: Expected %r but PR author is %r',
                                     assignee, api.creator)
                    # Currently, we just drop a notification in the PR
                    api.post_comment(POSSIBLE_DUP % number)

    elif (action == 'created' and                       # comment
          payload.get('pull_request') is None):
        msg = payload['comment']['body']
        match = re.search(r'@%s(?:\[bot\])?[: ]*assign (.*)' % api.name, str(msg.lower()))
        if match:
            name = match.group(1).split(' ')[0]
            if name == 'me':
                if 'c-assigned' in api.labels:
                    api.logger.debug('Assignee collision. Leaving it to core contributor...')
                    api.post_comment(RESPONSE_FAIL)
                else:
                    api.logger.debug('Got assign request. Assigning to %r', api.creator)
                    api.update_labels(add=['C-assigned'])
                    api.post_comment(RESPONSE_OK % api.creator)
                    # Mutate data only if we have the data
                    if is_issue_in_data:
                        data['issues'][api.issue_number]['assignee'] = api.creator
                        data['issues'][api.issue_number]['status'] = 'assigned'
                        data['issues'][api.issue_number]['last_active'] = payload['comment']['updated_at']
            else:
                # FIXME: Make core-contributors assign issues for people
                # and update local JSON store from their comment.
                # For this to work, we should get the core contributors through the API.
                # (Maintain a dump, or make a request once we encounter the first payload?)
                pass
        elif is_issue_in_data:
            # FIXME: Someone has commented in the issue. Multiple things to investigate.
            # What if the assignee had asked some question and no one answered?
            # What if the issue gets blocked on something else?
            # For now, we assume that our reviewers don't leave an issue/PR unnoticed for 4 days!
            # Maybe we could have another handler for pinging the reviewer if a question
            # remains unanswered for a while.
            data['issues'][api.issue_number]['last_active'] = payload['comment']['updated_at']
            if data['issues'][api.issue_number]['status'] == 'commented':
                if data['issues'][api.issue_number]['pr_number'] is None:
                    data['issues'][api.issue_number]['status'] = 'assigned'
                else:
                    data['issues'][api.issue_number]['status'] = 'pull'

    elif action == 'closed':
        if ('e-easy' in api.labels and is_issue_in_data):
            api.logger.debug('Issue #%s is being closed. Removing related data...')
            data['issues'].pop(api.issue_number)
        elif (payload.get('pull_request') and
              any(i['pr_number'] == api.issue_number for i in data['issues'])):
            comment = PR_ADDRESS_MSG % api.issue_number + ISSUE_UNASSIGN_MSG
            api.post_comment(comment)
            api.update_labels(remove=['C-assigned'])
            data['issues'][api.issue_number] = ISSUE_OBJ_DEFAULT

    elif action == 'reopened':      # FIXME: Also handle reopening issues?
        pass

    elif (action == 'labeled' and
          payload.get('pull_request') is None):
        label = payload['label']['name'].lower()
        if label == 'e-easy':
            api.logger.debug('Issue #%s has been marked E-easy. Posting welcome comment...',
                              api.issue_number)
            data['issues'][api.issue_number] = ISSUE_OBJ_DEFAULT
            api.post_comment(ASSIGN_MSG % api.name)
        elif label == 'c-assigned' and is_issue_in_data:
            api.logger.debug('Issue #%s has been assigned to... someone?', api.issue_number)
            data['issues'][api.issue_number]['assignee'] = '0xdeadbeef'

    elif (action == 'unlabeled' and is_issue_in_data and
          payload.get('pull_request') is None):
        if payload['label']['name'].lower() == 'e-easy':
            api.logger.debug('Issue #%s is no longer E-easy. Removing related data...',
                             api.issue_number)
            data['issues'].pop(api.issue_number)
        elif payload['label']['name'].lower() == 'c-assigned':
            api.logger.debug('Issue #%s has been unassigned. Setting issue to default data...',
                             api.issue_number)
            data['issues'][api.issue_number] = ISSUE_OBJ_DEFAULT

    elif action is None:    # check the timestamps and post comments as necessary
        if data.get('owner') and data.get('repo'):
            api.owner, api.repo = data['owner'], data['repo']
        else:   # We pass a fake payload here (so, owner and repo should be valid to proceed)
            api.logger.debug('No info about owner and repo in JSON. Skipping this cycle...')
            return

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
            if (now - last_active).days <= MAX_DAYS:
                api.logger.debug('Issue #%s is stil in grace period', number)
                continue

            api.logger.debug("Issue #%s has had its time. Something's gonna happen.", number)
            api.issue_number = number
            assignee = issue['assignee']
            data['issues'][number]['last_active'] = str(now)

            if status == 'assigned':
                api.logger.debug('Pinging %r in issue #%s', assignee, number)
                if assignee == '0xdeadbeef':
                    api.post_comment(ISSUE_ANON_PING)
                else:
                    api.post_comment(ISSUE_PING_MSG % assignee)
                data['issues'][number]['status'] = 'commented'
            elif status == 'commented' and status != 'pull':    # PR will be taken care of by another handler
                api.logger.debug('Unassigning issue #%s after grace period', number)
                api.update_labels(remove=['C-assigned'])
                api.post_comment(ISSUE_UNASSIGN_MSG)
                data['issues'][number] = ISSUE_OBJ_DEFAULT      # reset data

    if data != old_data:
        db.write_obj(data, inst_id, self_name)


REPO_SPECIFIC_HANDLERS = {
    "servo/servo": check_easy_issues
}

def easy_issues(api, _config, db, name):
    handler = api.get_matches_from_config(REPO_SPECIFIC_HANDLERS)
    if handler:
        handler(api, db, name)


methods = [easy_issues]
