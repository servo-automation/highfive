from ... import EventHandler, Modifier
from copy import deepcopy
from datetime import datetime
from dateutil.parser import parse as datetime_parse

import json, os, re

def default():      # create a new value every call, so that the values don't get overridden
    return {
        'assignee': None,
        'status': None,         # None || 'assigned' || 'pull' || 'commented'
        'last_active': None,
        'pr_number': None,
    }


class EasyIssueAssigner(EventHandler):
    '''
    This is a stateful handler. It tracks newcomer-friendly issues (also called "easy" issues),
    assigns them to the newcomers (based on their request), pings them when they haven't responded
    over a set period of time, tracks their PRs and once they've run out of time, it links the PR
    (if required) and unassigns them from the issue.
    '''

    def __init__(self, api, config):
        super(EasyIssueAssigner, self).__init__(api, config)
        self.__init_store_data()
        self.payload_issue_in_store = self.data['issues'].has_key(self.api.number) if self.api.number else None
        self.anonymous_name = '__deadbeef__'
        self.reviewers = self.get_matches_from_config(self.api.config.collaborators)

    def __init_store_data(self):
        '''Initialize store data and set defaults if necessary.'''

        data = self.get_object()
        if data.get('issues') is None:
            data['issues'] = {}
        if data.get('owner') is None and self.api.owner:
            data['owner'] = self.api.owner
        if data.get('repo') is None and self.api.repo:
            data['repo'] = self.api.repo
        self.data = data
        self.old_data = deepcopy(self.data)


    def on_issue_reopen(self):
        if self.api.is_pull:
            self._on_pull_open_or_reopen()
        else:
            self._on_issue_open_or_reopen()


    def on_issue_open(self):
        if self.api.is_pull:
            self._on_pull_open_or_reopen()
        else:
            self._on_issue_open_or_reopen()


    def on_new_comment(self):
        if self.api.is_pull:
            return

        message = self.api.comment.lower()
        match = re.search(r'@%s(?:\[bot\])?[: ]*assign @?(.*)' % self.api.name, message)
        if match:
            name = match.group(1).split(' ')[0]
            if name == 'me':
                self._on_selfish_request()
            else:
                self._on_graceful_request(target=name)
        elif self.payload_issue_in_store:
            # FIXME: Someone has commented in the issue. Multiple things to investigate.
            # What if the assignee had asked some question and no one answered?
            # What if the issue gets blocked on something else?
            # For now, we assume that our reviewers don't leave an easy issue unnoticed for 4 days!
            # Maybe we could have another handler for pinging the reviewer if a question
            # remains unanswered for a while.
            self.data['issues'][self.api.number]['last_active'] = self.api.payload['comment']['updated_at']
            if self.data['issues'][self.api.number]['status'] == 'commented':
                self.data['issues'][self.api.number]['status'] = 'assigned'


    def on_issue_closed(self):
        if self.payload_issue_in_store:
            self.logger.info('Issue #%s is being closed. Removing related data...', self.api.number)
            self.data['issues'].pop(self.api.number)

        elif self.api.is_pull:
            pull_number = self.api.number
            match = filter(lambda (_, i): i['pr_number'] == pull_number, self.data['issues'].items())
            if match:
                issue_number = match[0][0]
            else:
                return

            if self.api.sender == self.api.creator:
                self.logger.info('PR #%s is being closed by its author. Keeping issue assigned...')
                self.data['issues'][issue_number]['status'] = 'assigned'
                self.data['issues'][issue_number]['last_active'] = self.api.payload['pull_request']['updated_at']
                self.data['issues'][issue_number]['pr_number'] = None
            else:
                config = self.get_matched_subconfig()
                self.logger.info('PR #%s has been closed by a collaborator. Removing related data...', pull_number)
                comment = self.api.rand_choice(config['previous_work']) + ' ' + self.api.rand_choice(config['issue_unassign'])

                # This is a PR. Since we have to comment on the issue, we use a modifier.
                with Modifier(self.api, number=issue_number):
                    self.api.post_comment(comment.format(author=self.api.creator, pull=pull_number))
                    self.api.update_labels(remove=[config['assign_label']])

                self.data['issues'][issue_number] = default()


    def on_issue_label_add(self):
        if self.api.is_pull:
            return

        config = self.get_matched_subconfig()
        if self.api.current_label == config['easy_label'] and not self.payload_issue_in_store:
            # NOTE: We also make sure that the issue isn't in our data (since we do the
            # same thing when an issue is opened with an easy label).
            self.logger.debug('Issue #%s has been marked %s. Posting welcome comment...',
                              self.api.number, config['easy_label'])
            self.data['issues'][self.api.number] = default()
            comment = self.api.rand_choice(config['issue_assign'])
            self.api.post_comment(comment.format(bot=self.api.name))

        elif self.api.current_label == config['assign_label']:
            self.logger.debug('Issue #%s has been assigned to... someone?', self.api.number)
            # We always override here, because labels can be added only by collaborators and
            # so, their decision is final.
            if not self.payload_issue_in_store:
                self.data['issues'][self.api.number] = default()

            self.data['issues'][self.api.number]['assignee'] = self.anonymous_name
            self.data['issues'][self.api.number]['status'] = 'assigned'
            self.data['issues'][self.api.number]['last_active'] = self.api.payload['issue']['updated_at']


    def on_issue_label_remove(self):
        if self.api.is_pull:
            return

        config = self.get_matched_subconfig()
        if self.api.current_label == config['easy_label'] and self.payload_issue_in_store:
            self.logger.debug('Issue #%s is no longer %s. Removing related data...',
                              self.api.number, config['easy_label'])
            self.data['issues'].pop(self.api.number)
        elif self.api.current_label == config['assign_label']:
            self.logger.debug('Issue #%s has been unassigned. Setting issue to default data...',
                              self.api.number)
            self.data['issues'][self.api.number] = default()


    def on_next_tick(self):
        if self.data.get('owner') is None or self.data.get('repo') is None:
            self.logger.debug('No info about owner and/or repo in JSON. Skipping this cycle...')
            return

        with Modifier(self.api, owner=self.data['owner'], repo=self.data['repo']):
            self._check_issue_states()


    def _check_issue_states(self):
        # Note that the `api` class beyond this point shouldn't be trusted for anything more than
        # the names of owner, repo and its methods. All other variables are invalid.
        config = self.get_matched_subconfig()
        if not config:
            return

        for number, issue in self.data['issues'].iteritems():
            status = issue['status']
            last_active = issue['last_active']
            if not last_active:
                continue

            last_active = datetime_parse(last_active)
            now = datetime.now(last_active.tzinfo)
            if (now - last_active).days <= config['grace_period_days']:
                self.logger.debug('Issue #%s is stil in grace period', number)
                continue
            elif status == 'pull':      # PR handler will take care of this
                continue

            self.logger.info("Issue #%s has had its time. Something's gonna happen.", number)
            assignee = issue['assignee']
            self.data['issues'][number]['last_active'] = str(now)

            with Modifier(self.api, number=number):
                if status == 'assigned':
                    self.logger.info('Pinging %r in issue #%s', assignee, number)
                    if assignee == self.anonymous_name:
                        comment = self.api.rand_choice(config['unknown_ping'])
                        self.api.post_comment(comment)
                    else:
                        comment = self.api.rand_choice(config['known_ping']).format(assignee=assignee)
                        self.api.post_comment(comment)
                    self.data['issues'][number]['status'] = 'commented'

                elif status == 'commented':
                    self.logger.info('Unassigning issue #%s after grace period', number)
                    self.api.update_labels(remove=[config['assign_label']])
                    self.api.post_comment(self.api.rand_choice(config['issue_unassign']))
                    self.data['issues'][number] = default()


    def cleanup(self):
        if self.data != self.old_data:
            self.write_object(self.data)

    # Private methods

    def _on_issue_open_or_reopen(self):
        config = self.get_matched_subconfig()
        # It's an issue and it contains appropriate labels
        if config['easy_label'] in self.api.labels:
            if config['assign_label'] in self.api.labels:
                self.logger.info('Issue #%s has been assigned to someone (while opening)', self.api.number)
                self.data['issues'][self.api.number] = default()
                self.data['issues'][self.api.number]['assignee'] = self.anonymous_name
                self.data['issues'][self.api.number]['status'] = 'assigned'
                self.data['issues'][self.api.number]['last_active'] = self.api.payload['issue']['updated_at']
            else:
                self.logger.info('Issue #%s has been marked as easy (while opening). Posting welcome comment...',
                                 self.api.number)
                self.data['issues'][self.api.number] = default()


    def _on_pull_open_or_reopen(self):
        config = self.get_matched_subconfig()
        pr_body = self.api.payload['pull_request']['body']
        # check whether the PR addresses an issue in our store
        match = re.search(r'(?:fixe?|close|resolve)[s|d]? #([0-9]*)', str(pr_body))
        number = match.group(1) if match else None
        if not number or not self.data['issues'].has_key(number):
            return

        self.logger.info('PR #%s addresses issue #%s', self.api.number, number)
        assignee = self.data['issues'][number]['assignee']
        if assignee == self.anonymous_name:
            # Assume that this author is the anonymous assignee
            assignee = self.api.creator

        self.data['issues'][number]['assignee'] = self.api.creator
        self.data['issues'][number]['pr_number'] = self.api.number
        self.data['issues'][number]['status'] = 'pull'
        self.data['issues'][number]['last_active'] = self.api.payload['pull_request']['updated_at']

        # PR author hasn't claimed the issue
        if assignee is None:
            self.logger.info('Assignee has not requested issue assignment.'
                             ' Marking issue as assigned')
            self.api.post_comment(self.api.rand_choice(config['dup_effort']))
            with Modifier(self.api, number=number):
                self.api.update_labels(add=[config['assign_label']])

        # PR author isn't the assignee
        elif self.api.creator != assignee:
            self.logger.info('Assignee collision: Expected %r but PR author is %r',
                             assignee, self.api.creator)
            # Currently, we just drop a notification in the PR
            comment = self.api.rand_choice(config['possible_dup'])
            self.api.post_comment(comment.format(issue=number))


    def _on_selfish_request(self):
        config = self.get_matched_subconfig()
        if config['assign_label'] in self.api.labels:
            if not self.payload_issue_in_store:
                self.data['issues'][self.api.number] = default()
                self.data['issues'][self.api.number]['assignee'] = self.anonymous_name

            self.data['issues'][self.api.number]['status'] = 'assigned'
            self.data['issues'][self.api.number]['last_active'] = self.api.payload['comment']['updated_at']

            self.logger.debug('Assignee collision. Leaving it to core contributor...')
            self.api.post_comment(self.api.rand_choice(config['assign_fail']))
        else:
            # This way, assigning applies to "any" issue. If it's assigned, then
            # highfive will start tracking those issues and the associating PRs.
            if not self.payload_issue_in_store:
                self.data['issues'][self.api.number] = default()

            self.logger.debug('Got assign request. Assigning to %r', self.api.sender)
            self.api.update_labels(add=[config['assign_label']])
            comment = self.api.rand_choice(config['assign_success'])
            self.api.post_comment(comment.format(assignee=self.api.sender))

            self.data['issues'][self.api.number]['assignee'] = self.api.sender
            self.data['issues'][self.api.number]['status'] = 'assigned'
            self.data['issues'][self.api.number]['last_active'] = self.api.payload['comment']['updated_at']


    def _on_graceful_request(self, target):
        config = self.get_matched_subconfig()
        if self.api.sender in self.reviewers:
            self.logger.debug('Got assign request from reviewer. Assigning to %r', target)
            self.data['issues'][self.api.number] = default()
            self.data['issues'][self.api.number]['assignee'] = target
            self.data['issues'][self.api.number]['status'] = 'assigned'
            self.data['issues'][self.api.number]['last_active'] = self.api.payload['comment']['updated_at']
            self.api.update_labels(add=[config['assign_label']])
            self.api.post_comment(self.api.rand_choice(config['assign_success']).format(assignee=target))
        else:
            self.api.post_comment(self.api.rand_choice(config['non_reviewer_ack']))


handler = EasyIssueAssigner
