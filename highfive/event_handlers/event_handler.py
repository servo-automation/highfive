from ..runner.config import get_logger

from copy import deepcopy

import random
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

        # Internally used actions
        '__tick'      : 'on_next_tick',
    }

    def __init__(self, api, config):
        self.name = self.__class__.__name__
        self.api = api
        self.config = config
        self.logger = get_logger(__name__)

    # Helper methods used throughout handlers

    def find_reviewers(self, comment):
        '''
        If the user had specified the reviewer(s), then return the name(s),
        otherwise return None. It matches all the usernames following a
        review request.

        For example,
        "r? @foo r? @bar and cc @foobar"
        "r? @foo I've done blah blah r? @bar for baz"

        Both these comments return ['foo', 'bar']
        '''
        return re.findall('r\? @?([A-Za-z0-9]+)', str(comment), re.DOTALL)

    def get_matched_subconfig(self):
        '''
        While all handlers can filter payloads based on "allowed_repos", some handlers
        support per-repo configuration. This gets the sub-config (from the actual handler config)
        for a handler based on its repo in the payload.
        '''

        return self.get_matches_from_config(self.config)

    def get_matches_from_config(self, config):
        '''Filter the given per-repo configuration based on the payload's owner and repo.'''

        if not (self.api.owner and self.api.repo):
            self.logger.error("There's no owner/repo info in payload. Bleh?")
            return None

        result = None
        string = '%s/%s' % (self.api.owner, self.api.repo)
        for pattern in config:
            if re.search(pattern.lower(), string):
                if not result:
                    result = deepcopy(config[pattern])
                elif isinstance(result, list):
                    result.extend(config[pattern])
                elif isinstance(result, dict):
                    result.update(config[pattern])

        return result

    def join_names(self, names):
        ''' Join multiple words in human-readable form'''

        if len(names) == 1:
            return names.pop()
        elif len(names) == 2:
            return '{} and {}'.format(*names)
        elif len(names) > 2:
            last = names.pop()
            return '%s and %s' % (', '.join(names), last)
        return ''

    # Wrapper methods over `InstallationStore` methods. This way, the handlers don't have to worry
    # about keys for their data.

    def get_object(self):
        '''Get the object associated with this handler.'''

        if not self.api.store:
            return {}

        key = self.name
        return self.api.store.get_object(key)

    def remove_object(self):
        '''Remove the object associated with this handler.'''

        if not self.api.store:
            return

        key = self.name
        self.api.store.remove_object(key)

    def write_object(self, data, key=''):
        '''Write data to the object associated with this handler.'''

        if not self.api.store:
            return

        key = self.name
        self.api.store.write_object(key, data)

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

    def on_next_tick(self):
        '''
        Since the handlers aren't aware of date/time, this event is for those handlers that depend
        on "time" - it's externally called by the daemon thread every now and then in a loop.
        '''
        pass

    def reset(self):
        '''Overridable method before handling payload to reset the internal properties (if any)'''
        pass

    def cleanup(self):
        '''Overridable method to cleanup the handler after handling a payload.'''
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
            self.reset()
            getattr(self, method)()
            self.cleanup()
