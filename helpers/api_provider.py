from base64 import standard_b64encode as b64_encode
from gzip import GzipFile

from methods import Shared, get_path_parent

import json, urllib2


class APIProvider(object):
    def __init__(self, payload):
        self.payload = payload
        self.shared = Shared()
        self.pull_url = payload['pull_request']['url'] if payload.get('pull_request') else None
        self.diff = None

        node = self.get_matching_path(['owner', 'login'])
        self.owner = node['owner']['login'].lower()
        self.repo = node['name'].lower()

        node = self.get_matching_path(['number'])
        self.issue_number = node.get('number')

        # Github labels are unique and case-insensitive (which is really helpful!)
        node = self.get_matching_path(['labels'])
        self.labels = map(lambda obj: obj['name'].lower(), node.get('labels', []))

    def get_matching_path(self, matches):   # making the helper available for handlers
        return get_path_parent(self.payload, matches)

    def get_sender_and_creator(self):
        sender = self.payload['sender']['login'].lower()    # who triggered the payload?
        node = self.get_matching_path(['user', 'login']) or {'user': {'login': ''}}
        creator = node['user']['login'].lower()     # (optional) creator of issue/pull
        return sender, creator

    # Per-repo configuration (FIXME: go for regex?)
    def get_matches_from_config(self, config):
        repos = []
        for repo in config:
            # Initially, assume that it's a wildcard match (for all owners and repos)
            watcher_owner, watcher_repo = self.owner, self.repo

            split = repo.lower().split('/')
            if len(split) == 2:
                watcher_owner = split[0]
                # match for all repos owned by a particular owner
                watcher_repo = self.repo if split[1] == '*' else split[1]
            elif split[0] != '*':
                continue            # invalid format

            if watcher_owner == self.owner and watcher_repo == self.repo:
                repos.append(config[repo])

        return repos

    def get_labels(self):
        raise NotImplementedError

    def replace_labels(self, labels=[]):
        raise NotImplementedError

    def update_labels(self, added=[], removed=[]):
        to_lower = lambda label: label.lower()
        current_labels = set(map(to_lower, self.labels))
        current_labels.update(map(to_lower, added))
        current_labels.difference_update(map(to_lower, removed))
        self.replace_labels(list(current_labels))

    def get_pull(self):
        raise NotImplementedError

    def get_diff(self):
        raise NotImplementedError

    def get_added_lines(self):
        diff = self.get_diff()
        for line in diff.splitlines():
            if line.startswith('+') and not line.startswith('+++'):
                yield line

    def post_comment(self, comment):
        raise NotImplementedError

    def set_assignees(self, assignees):
        raise NotImplementedError


class GithubAPIProvider(APIProvider):
    base_url = 'https://api.github.com/repos/'
    issue_url = base_url + '%s/%s/issues/%s/'
    comments_post_url = issue_url + 'comments'
    labels_url = issue_url + 'labels'
    assignees_url = issue_url + 'assignees'
    diff_url = 'https://github.com/%s/%s/pull/%s.diff'

    def __init__(self, payload, user, token):
        self.user = user
        self.token = token
        super(GithubAPIProvider, self).__init__(payload)

    # self-helpers

    def _request(self, method, url, data=None):
        data = None if not data else json.dumps(data)
        headers = {} if not data else {'Content-Type': 'application/json'}
        req = urllib2.Request(url, data, headers)
        authorization = '%s:%s' % (self.user, self.token)
        base64 = b64_encode(authorization).replace('\n', '')
        req.add_header('Authorization', 'Basic %s' % base64)

        resp = urllib2.urlopen(req)
        header = resp.info()
        if header.get('Content-Encoding') == 'gzip':
            resp = GzipFile(fileobj=resp)
        return (header, resp.read())

    def _handle_labels(self, method, labels=[]):
        url = self.labels_url % (self.owner, self.repo, self.issue_number)
        _header, body = self._request(method, url, labels)
        labels = map(lambda obj: obj['name'].lower(), json.loads(body))
        return labels

    # handler helpers

    def get_labels(self):
        if self.labels:
            return self.labels

        self.labels = self._handle_labels('GET')
        return self.labels

    # passing an empty list clears all the existing labels
    def replace_labels(self, labels=[]):
        self.labels = self._handle_labels('PUT', labels)

    def get_pull(self):
        _headers, body = self._request('GET', self.pull_url)
        return body

    def get_diff(self):
        if self.diff:
            return self.diff

        url = self.diff_url % (self.owner, self.repo, self.issue_number)
        _headers, self.diff = self._request('GET', url)
        return self.diff

    def post_comment(self, comment):
        url = self.comments_post_url % (self.owner, self.repo, self.issue_number)
        try:
            self._request('POST', url, {'body': comment})
        except urllib2.HTTPError as err:
            if err.code != 201:
                raise err

    def set_assignees(self, assignees):
        url = self.assignees_url % (self.owner, self.repo, self.issue_number)
        try:
            self._request('POST', url, {'assignees': assignees})
        except urllib2.HTTPError as err:
            if err.code != 201:
                raise err
