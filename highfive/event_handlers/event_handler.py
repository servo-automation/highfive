class EventHandler(object):
    # NOTE: Github doesn't differentiate between issue events and PR events unless the event
    # has something to do with the PR itself (like pushing commit, triggering build, etc.).
    # Things like assigning, closing, labeling, etc. happen the same way for issue and PR.
    # All PR events other than comments have "pull_request" key in the payload.
    #
    # For comments, it's confusing because it has the "issue" key in its payload, but the issue
    # number may actually be a PR (if the comment was left in a PR). Dear Github, this is sad.
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
