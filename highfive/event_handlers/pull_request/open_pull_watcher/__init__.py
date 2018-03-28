from ... import EventHandler, Modifier
from copy import deepcopy
from datetime import datetime
from dateutil.parser import parse as datetime_parse

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


class OpenPullWatcher(EventHandler):
    '''
    A stateful handler which tracks pull requests and pings the reviewers and assignees when PRs
    are prone to be inactive.
    '''

    def __init__(self, api, config):
        super(OpenPullWatcher, self).__init__(api, config)
        self._load_pr_list()
        self.data = default()
        self.store_has_pull = self.api.number in self.pr_list['pulls']

        if self.store_has_pull:
            data = self.get_object(key=self.api.number)
            if data:
                self.data = data

        self.old_data = deepcopy(self.data)


    def _load_pr_list(self):
        '''
        Initialize store data and set defaults if necessary.

        Firstly, it needs the list of active PRs, for which it uses this handler's data object
        directly. Then, it needs the actual PR data, for which it uses the PR number as the key.
        '''

        data = self.get_object()
        if data.get('owner') is None and self.api.owner:
            data['owner'] = self.api.owner
        if data.get('repo') is None and self.api.repo:
            data['repo'] = self.api.repo
        if data.get('pulls') is None:
            data['pulls'] = []
        self.pr_list = data
        self.old_list = deepcopy(data)


    def on_new_comment(self):
        if not self.store_has_pull:
            return

        self.data['last_active'] = self.api.last_updated
        self.data['status'] = None
        self.data['comments'].append({
            'body': self.api.comment,
            'when': self.api.last_updated,
            'who': self.api.sender
        })


    def on_pr_update(self):
        if not self.store_has_pull:
            return

        self.data['last_push'] = self.data['last_active'] = self.api.last_updated
        self.data['status'] = None


    def on_issue_reopen(self):
        if not self.api.is_pull:
            return

        self._on_pull_open_or_reopen()


    def on_issue_assign(self):
        if not self.store_has_pull:
            return

        self._on_pull_assign_or_unassign()


    def on_issue_unassign(self):
        if not self.store_has_pull:
            return

        self._on_pull_assign_or_unassign()


    def on_issue_open(self):
        if not self.api.is_pull:
            return

        self._on_pull_open_or_reopen()


    def on_issue_closed(self):
        if not self.store_has_pull:
            return

        self.logger.info('PR #%s closed. Removing JSON...', self.api.number)
        self.pr_list['pulls'].remove(self.api.number)


    def on_issue_label_add(self):
        if not self.store_has_pull:
            return

        self.data['labels'] = list(set(self.data['labels']).union(self.api.current_label))


    def on_issue_label_remove(self):
        if not self.store_has_pull:
            return

        self.data['labels'] = list(set(self.data['labels']).difference(self.api.current_label))


    def on_next_tick(self):
        if self.pr_list.get('owner') is None or self.pr_list.get('repo') is None:
            self.logger.debug('No info about owner and/or repo in JSON. Skipping this cycle...')
            return

        with Modifier(self.api, owner=self.pr_list['owner'], repo=self.pr_list['repo']):
            self._check_pulls()

        # Since this handler deals with multiple data objects, we don't have anything in particular
        # in the end. We reset this so that we don't write any date anywhere during cleanup.
        self.api.number = None


    def cleanup(self):
        if self.pr_list != self.old_list:
            self.write_object(self.pr_list)
        # Since we're identifying PR data based on key, we write only when the PR number exists.
        if self.api.number and self.old_data != self.data:
            self.write_object(self.data, key=self.api.number)


    def _check_pulls(self):
        config = self.get_matched_subconfig()
        if not config:
            return

        for number in self.pr_list['pulls']:
            self.data = self.get_object(key=number)
            self.old_data = deepcopy(self.data)
            last_active = self.data.get('last_active')
            if not last_active:
                continue

            last_active = datetime_parse(last_active)
            now = datetime.now(last_active.tzinfo)
            if (now - last_active).days <= config['grace_period_days']:
                self.logger.debug('PR #%s is stil in grace period', number)
                continue

            self.logger.info("PR #%s has had its time. Something's gonna happen.", number)
            self.data['last_active'] = str(now)

            with Modifier(self.api, number=number):
                self._handle_indiscipline_pr(config)

            if self.old_data != self.data:
                self.write_object(self.data, key=number)


    def _handle_indiscipline_pr(self, config):
        status = self.data.get('status')
        if not self.data['assignee']:
            # Assign someone randomly if we don't find an assignee after grace period
            reviewers = filter(lambda name: name.lower() != self.data['author'],
                               self.get_matches_from_config(self.api.config.collaborators))
            new_assignee = self.api.rand_choice(reviewers)
            self.api.set_assignees([new_assignee])
            comment = self.api.rand_choice(config['review_ping'])
            self.api.post_comment(comment.format(reviewer=new_assignee))
            return

        if status is None:
            self._on_first_grace(config)
        elif status == 'commented':
            self.logger.info('Closing PR #%s after grace period', self.api.number)
            comment = self.api.rand_choice(config['pr_close'])
            self.api.post_comment(comment.format(author=self.data['author']))
            self.api.close_issue()
            self.pr_list['pulls'].remove(self.api.number)
            self.data['status'] = 'closed'


    def _on_first_grace(self, config):
        should_ping_reviewer = False
        assignee_comments = filter(lambda d: d['who'] == self.data['assignee'], self.data['comments'])
        author_comments = filter(lambda d: d['who'] == self.data['author'], self.data['comments'])
        if not assignee_comments:
            # Reviewer hasn't commented at all!
            should_ping_reviewer = True
        else:
            last_review = datetime_parse(assignee_comments[-1]['when'])
            last_push = datetime_parse(self.data['last_push'])
            if last_review < last_push:
                # Reviewer hasn't looked at this since the last push
                should_ping_reviewer = True
            elif not author_comments:
                # Author hasn't commented at all!
                comment = self.api.rand_choice(config['pr_ping'])
                self.api.post_comment(comment.format(author=self.data['author']))
                self.data['status'] = 'commented'
            else:
                # It could be waiting on the assignee or the author. Right now, we just poke them both.
                self.api.post_comment(self.api.rand_choice(config['pr_anon_ping']))

        if should_ping_reviewer:
            # Right now, we just ping the reviewer until he takes a look at this or assigns someone else
            comment = self.api.rand_choice(config['review_ping'])
            self.api.post_comment(comment.format(reviewer=self.data['assignee']))


    def _on_pull_assign_or_unassign(self):
        self.data['assignee'] = self.api.assignee
        self.data['last_active'] = self.api.last_updated


    def _on_pull_open_or_reopen(self):
        self.pr_list['pulls'].append(self.api.number)
        self.data['author'] = self.api.creator
        self.data['number'] = self.api.number
        self.data['labels'] = self.api.labels
        self.data['body'] = self.api.payload['pull_request']['body']
        self.data['assignee'] = self.api.assignee
        self.data['last_push'] = self.data['last_active'] = self.api.last_updated


handler = OpenPullWatcher
