from ..runner.config import get_logger

import re

class EventHandler(object):
    '''
    Interface object for handlers. Every Github payload is associated with an action. This interface
    has the actions and their corresponding methods. The handlers inherit from this interface and
    override these methods. Once we've initialized a handler, we call `handle_payload` which calls
    the method corresponding to the action.
    '''
    # NOTE: Github doesn't differentiate between issue events and PR events unless the event
    # has something to do with the PR itself (like pushing commit, triggering build, etc.).
    # Things like assigning, closing, labeling, etc. happen the same way for issue and PR.
    # All PR events other than comments have "pull_request" key in the payload.
    #
    # For comments, it's confusing because it has the "issue" key in its payload, but the issue
    # may actually be a PR (if the comment was left in a PR). Dear Github, this is sad.
    actions = {
        'assigned'    : 'on_issue_assign',
        'unassigned'  : 'on_issue_unassign',
        'opened'      : 'on_issue_open',
        'closed'      : 'on_issue_closed',
        'reopened'    : 'on_issue_reopen',
        'synchronize' : 'on_pr_update',
        'created'     : 'on_new_comment',
        'labeled'     : 'on_issue_label_add',
        'unlabeled'   : 'on_issue_label_remove',
    }

    def __init__(self, api, config):
        self.api = api
        self.config = config
        self.logger = get_logger(__name__)

    # Methods corresponding to the actions

    def on_issue_assign(self):
        pass

    def on_issue_unassign(self):
        pass

    def on_issue_open(self):
        pass

    def on_issue_closed(self):
        pass

    def on_issue_reopen(self):
        pass

    def on_pr_update(self):
        pass

    def on_new_comment(self):
        pass

    def on_issue_label_add(self):
        pass

    def on_issue_label_remove(self):
        pass

    def handle_payload(self):
        '''Call the method corresponding to the payload's action.'''

        if not self.config.get('active'):       # pre-check whether the handler is active
            return

        # Check if the handler can only be used in specific patterns of repos.
        allowed_repos = self.config.get('allowed_repos', [])
        this_repo = '%s/%s' % (self.api.owner, self.api.repo)
        if allowed_repos and not any(re.search(pat, this_repo) for pat in allowed_repos):
            return

        method = self.actions.get(self.api.payload['action'])
        if method is not None:
            getattr(self, method)()
