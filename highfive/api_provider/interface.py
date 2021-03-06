from ..runner.config import get_logger
from ..runner.request import request_with_requests

from datetime import datetime
from dateutil.parser import parse as datetime_parse

import random

DEFAULTS = ['pull_url', 'is_open', 'is_pull', 'creator', 'last_updated', 'number', 'diff',
            'sender', 'owner', 'repo', 'current_label', 'assignee', 'comment']
LIST_DEFAULTS = ['labels']
CONTRIBUTORS_STORE_KEY = '__contributors__'
CONTRIBUTORS_UPDATE_INTERVAL_HOURS = 1

class APIProvider(object):
    '''
    The interface used by `GithubAPIProvider` object to take actions based on the incoming
    payload. API provider objects are tied to payloads.

    Once the runner receives a payload, an API provider object is created and sent to all
    handlers (through the installation manager). This object is supposed to provide encapsulation
    for commonly used payload attributes and methods, so that the handlers don't have to worry
    about extracting them every time.
    '''

    imgur_post_url = 'https://api.imgur.com/3/image'

    def __init__(self, config, payload, store=None):
        self.name = config.name
        self.config = config
        self.payload = payload
        self.logger = get_logger(__name__)
        self.store = store

        for attr in DEFAULTS:
            setattr(self, attr, None)

        for attr in LIST_DEFAULTS:
            setattr(self, attr, [])

        if payload.get('repository'):
            self.owner = payload['repository']['owner']['login']
            self.repo = payload['repository']['name']
        else:
            self.logger.error('Error getting repository information from payload.')

        if payload.get('sender'):
            self.sender = payload['sender']['login'].lower()

        if payload.get('label'):
            self.current_label = payload['label']['name'].lower()

        if payload.get('pull_request'):
            self._init_pull_attributes()
        elif payload.get('issue'):
            self._init_issue_attributes()

        if payload.get('comment'):
            self._init_comment_attributes()

    # Methods for initialization

    def _init_issue_attributes(self):
        issue = self.payload['issue']
        self.creator = issue['user']['login'].lower()
        self.is_open = issue['state'].lower() == 'open'
        self.last_updated = issue.get('updated_at')
        # Issue and PR numbers are strings, because it we use issues as keys in our store
        # and JSON keys should be strings (otherwise, test suite breaks).
        self.number = str(issue['number'])
        self.labels = map(lambda obj: obj['name'].lower(), issue['labels'])

    def _init_pull_attributes(self):
        self.is_pull = True
        pull = self.payload['pull_request']

        if pull.get('assignee'):
            self.assignee = pull['assignee']['login'].lower()

        self.pull_url = pull['url']
        self.creator = pull['user']['login'].lower()
        self.is_open = pull['state'] == 'open'
        self.last_updated = pull.get('updated_at')
        self.number = str(pull['number'])

    def _init_comment_attributes(self):
        self.comment = self.payload['comment']['body'].encode('utf-8')
        # Github API always shows comments as "issue comments" - there's no PR comments.
        # We have to find manually.
        issue = self.payload.get('issue', {})
        self.is_pull = issue.get("pull_request") is not None

    # Methods unrelated to the API (overridden only in test suite).

    def get_page_content(self, url):
        '''Get the contents from a given URL.'''

        resp = request_with_requests('GET', url)
        return resp.data

    def get_screenshots_for_build(self, build_url):
        url = self.config.get('servo_reftest_screenshot_endpoint', '')
        url.rstrip('/')
        url += '/?url=%s' % build_url   # FIXME: should probably url encode?
        resp = request_with_requests('GET', url)
        if resp.code != 200:
            self.logger.error('Error requesting %s' % url)
            return

        if not resp.is_json():
            self.logger.debug('Cannot decode JSON data from %s' % url)
            return

        return resp.data

    def post_image_to_imgur(self, base64_data, json_request=request_with_requests):
        '''
        If the client ID is present in configuration, then this method can be used to
        upload base64-encoded image data (anonymously) to Imgur and returns the permalink.
        '''

        if self.config.imgur_client_id is None:
            self.logger.error('Imgur client ID has not been set!')
            return

        headers = {'Authorization': 'Client-ID %s' % self.config.imgur_client_id}

        resp = json_request('POST', self.imgur_post_url,
                            data={'image': base64_data},
                            headers=headers)
        if resp.code != 200:
            self.logger.error('Error posting image to Imgur! Response: %s' % resp.data)
            return

        if not resp.is_json():
            self.logger.error('Cannot parse response from Imgur! Response: %s' % resp.data)
            return

        return resp.data['data']['link']

    # Overridable methods.

    def rand_choice(self, values):
        '''
        Choose a pseudo-random value from the given list of values. We use this
        so that we can override it during testing.
        '''

        return random.choice(values)

    def get_branch_head(self, branch):
        raise NotImplementedError

    def edit_comment(self, _id, comment):
        raise NotImplementedError

    def set_assignees(self, assignees):
        raise NotImplementedError

    def get_labels(self):
        raise NotImplementedError

    def replace_labels(self, labels=[]):
        raise NotImplementedError

    def post_comment(self, comment):
        raise NotImplementedError

    def get_diff(self):
        raise NotImplementedError

    def fetch_contributors(self):
        raise NotImplementedError

    def get_pull(self):
        raise NotImplementedError

    def close_issue(self):
        raise NotImplementedError

    # Default methods depending on the overriddable methods.

    def get_contributors(self, fetch=False):
        '''
        If `fetch` is disabled and if store exists, then this gets the contributors list from the
        store. Otherwise, this calls the overriddable method, gets the list, writes to the store
        (if it exists) and returns the list.
        '''

        now = datetime.now()

        if self.store:
            contributors = self.store.get_object(CONTRIBUTORS_STORE_KEY)
            if contributors:
                # Force fetch if last updated time is long back.
                timestamp = contributors.get('last_update_time', str(now))
                last_update = datetime_parse(timestamp)
                if (now - last_update).seconds >= CONTRIBUTORS_UPDATE_INTERVAL_HOURS * 3600:
                    fetch = True

            if contributors.get('list') and not fetch:
                return contributors['list']

        self.logger.info('Updating contributors list...')
        contributors = {
            'last_update_time': str(now),
            'list': self.fetch_contributors()
        }

        if self.store:
            self.store.write_object(CONTRIBUTORS_STORE_KEY, data=contributors)

        return contributors['list']

    def update_labels(self, add=[], remove=[]):
        '''
        This fetches the labels corresponding to the given payload, adds/subtracts
        labels based on the method call, and finally replaces all the labels in the issue/PR.
        Since this calls `get_labels` every time this method is called, it's up to the implementor
        to ensure that proper caching is done in that method.
        '''

        to_lower = lambda label: label.lower()      # str.lower doesn't work for unicode
        current_labels = set(map(to_lower, self.get_labels()))
        current_labels.update(map(to_lower, add))
        current_labels.difference_update(map(to_lower, remove))
        self.replace_labels(list(current_labels))

    def get_added_lines(self):
        '''Generator over the added lines in the commit diff.'''

        diff = self.get_diff()
        for line in diff.splitlines():
            if line.startswith('+') and not line.startswith('+++'):
                yield line

    def get_changed_files(self):
        '''Generator over the changed files in commit diff.'''

        diff = self.get_diff()
        for line in diff.splitlines():
            # Get paths from a line like 'diff --git a/path/to/file b/path/to/file'
            if line.startswith('diff --git '):
                file_paths = filter(lambda p: p.startswith('a/') or p.startswith('b/'),
                                    line.split())
                file_paths = set(map(lambda p: p[2:], file_paths))
                for path in file_paths:
                    yield path      # yields only one item atmost!

    def post_warning(self, comment):
        '''Post a warning comment.'''

        comment = ':warning: **Warning!** :warning:\n\n%s' % comment
        self.post_comment(comment)
