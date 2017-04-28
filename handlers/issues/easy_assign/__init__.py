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

POSSIBLE_DUP = ("**Note:** The assignee in #%s doesn't match with the"
                " name of author in this pull request.")

RESPONSE_FAIL = ('It looks like this has already been assigned to someone.'
                 ' I\'ll leave the decision to a core contributor.')

RESPONSE_OK = ('Hey @%s! Thanks for your interest in working on this issue.'
               ' It\'s now assigned to you!')

ISSUE_PING_MSG = 'Hey @%s! Did you look into this? You got any questions for us?'
PR_PING_MSG = 'Hey @%s! Are you planning to finish this off?'

PR_CLOSE_MSG = ("Okay, I'm gonna close this based on inactivity. If you change your mind"
                " about working on this issue again, feel free to ping us and we'll reopen"
                " it for you. Thanks for taking a stab at this :smile:")

PR_ADDRESS_MSG = 'Previous work on #%s. '
ISSUE_UNASSIGN_MSG = 'This is now open for anyone to jump in!'

ISSUE_OBJ_DEFAULT = {
    'assignee': None,
    'status': None,
    'last_active': None,
    'pr_number': None,
}

MAX_DAYS = 4


def _check_easy_issues(api, dump_path):
    payload = api.payload
    handler_json = os.path.join(dump_path, 'easy_issues.json')
    if not os.path.exists(handler_json):
        api.logger.info('Creating JSON file: %r', handler_json)
        with open(handler_json, 'w') as fd:
            json.dump({'issues': {}}, fd)

    with open(handler_json, 'r') as fd:     # NOTE: Investigate possible racing condition
        data = json.load(fd)
        api.logger.debug('Loading JSON data: %s', data)

    action = payload.get('action')
    if api.owner:
        data['owner'] = api.owner
    if api.repo:
        data['repo'] = api.repo

    if action == 'opened':                  # issue or PR
        if payload.get('pull_request'):
            pr_body = payload['pull_request']['body']
            # check whether the PR addresses an issue in our store
            match = re.search(r'(?:fixe?|close|resolve)[s|d]? #([0-9]*)', pr_body)
            number = match.group(1) if match else None
            if number and data['issues'].has_key(number):
                api.logger.debug('PR #%s addresses issue #%s', api.issue_number, number)
                assignee = data['issues'][number]['assignee']
                if api.creator != assignee:     # FIXME: What now?
                    api.logger.debug('Assignee collision: Expected %r but PR author is %r',
                                     assignee, api.creator)
                    api.post_comment(POSSIBLE_DUP % number)

                data['issues'][number]['assignee'] = api.creator
                data['issues'][number]['pr_number'] = api.issue_number
                data['issues'][number]['status'] = 'pull'
                data['issues'][number]['last_active'] = payload['pull_request']['updated_at']

                if assignee is None:
                    api.logger.debug('Assignee has not requested issue assignment.'
                                     ' Marking issue as assigned')
                    api.post_comment(DUP_EFFORT_MSG)
                    api.issue_number = number
                    api.update_labels(add=['C-assigned'])
        # FIXME: Investigate and uncomment/remove the code below (in the future).
        # This has been disabled because if an issue is opened "with" labels,
        # Github appears to send payloads for the issue (with the label info) and
        # for all the individual labels (which will result in posting the comment twice).
        elif 'e-easy' in api.labels and data['issues'].get(api.issue_number) is None:
            # data['issues'][api.issue_number] = ISSUE_OBJ_DEFAULT
            # api.logger.debug('Found E-easy label in issue. Posting welcome comment...')
            # api.post_comment(ASSIGN_MSG % api.name)
            pass

    elif action == 'created':               # comment
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
                    data['issues'][api.issue_number]['assignee'] = api.creator
                    data['issues'][api.issue_number]['status'] = 'assigned'
                    data['issues'][api.issue_number]['last_active'] = str(datetime.now())
                    api.post_comment(RESPONSE_OK % api.creator)
            else:
                # FIXME: Make core-contributors assign issues for people
                # and update local JSON store from their comment.
                pass

    elif action == 'closed':
        if ('e-easy' in api.labels and data['issues'].has_key(api.issue_number)):
            api.logger.debug('Issue #%s is being closed. Removing related data...')
            data['issues'].pop(api.issue_number)
        elif (payload.get('pull_request') and
              any(i['pr_number'] == api.issue_number for i in data['issues'])):
            # FIXME: What should we do if the assignee closes/reopens the PR?
            pass

    elif (action == 'labeled' and
          payload.get('pull_request') is None and                   # not a PR
          payload['label']['name'].lower() == 'e-easy'):            # marked E-easy
        api.logger.debug('Issue has been marked E-easy. Posting welcome comment...')
        data['issues'][api.issue_number] = ISSUE_OBJ_DEFAULT
        api.post_comment(ASSIGN_MSG % api.name)

    elif (action == 'unlabeled' and
          payload.get('pull_request') is None and
          payload['label']['name'].lower() == 'e-easy' and
          data['issues'].has_key(api.issue_number)):
        api.logger.debug('Issue is no longer E-easy. Removing related data...')
        data['issues'].pop(api.issue_number)

    elif action is None:    # check the timestamps and post comments as necessary
        if data.get('owner') and data.get('repo'):
            api.owner, api.repo = data['owner'], data['repo']
        else:   # We pass a fake payload here (so, owner and repo should be valid to progress)
            api.logger.debug('No info about owner and repo in JSON. Skipping this cycle...')
            return

        # Note that the `api` variable beyond this point shouldn't be trusted for
        # anything more than the names of owner, repo, its method and its logger.
        # All other variables are invalid.
        for number, issue in data['issues'].iteritems():
            status = issue['status']
            last_active = issue['last_active']
            if not last_active:
                continue

            last_active = datetime_parse(last_active)
            now = datetime.now(last_active.tzinfo)
            if (now - last_active).days <= MAX_DAYS:
                api.logger.debug('Issue %s is stil in grace period', number)
                continue

            api.issue_number = number
            assignee = issue['assignee']
            if status == 'pull':
                api.issue_number = issue['pr_number']
                api.post_comment(PR_PING_MSG % assignee)
                data['issues'][number]['status'] = 'commented'
            elif status == 'assigned':
                api.logger.debug('Pinging %r in issue #%s', assignee, number)
                api.post_comment(ISSUE_PING_MSG % assignee)
                data['issues'][number]['status'] = 'commented'
            elif status == 'commented':
                comment = ''
                pr_num = issue['pr_number']
                if pr_num:
                    api.logger.debug('Closing PR #%s after grace period', pr_num)
                    api.issue_number = pr_num
                    api.post_comment(PR_CLOSE_MSG)
                    api.close_issue()
                    comment = PR_ADDRESS_MSG % pr_num

                api.issue_number = number
                api.logger.debug('Unassigning issue #%s after grace period', number)
                api.update_labels(remove=['C-assigned'])
                comment += ISSUE_UNASSIGN_MSG
                api.post_comment(comment)       # reset data
                data['issues'][number] = ISSUE_OBJ_DEFAULT

    # FIXME: Create a MutationObserver-like object that wraps over a dict
    # and tells whether its contents have changed. That way, we won't have to
    # replace the JSON all the time! This is of minor impact, since (in reality)
    # we poke these handlers only once every hour or so
    with open(handler_json, 'w') as fd:
        api.logger.debug('Dumping JSON data... %s', data)
        json.dump(data, fd)


REPO_SPECIFIC_HANDLERS = {
    "servo/servo": {    # All these handlers are specific to Servo!
        "methods": [
            _check_easy_issues,
        ]
    },
}

def check_issues(api, config, dump_path):
    repos = config.get('repos', {})
    _config = api.get_matches_from_config(repos)

    # do some stuff (if config-based handlers are added in the future)

    handlers = api.get_matches_from_config(REPO_SPECIFIC_HANDLERS)
    for method in handlers.get('methods', []):
        method(api, dump_path)


methods = [check_issues]
