from base64 import standard_b64encode as b64_encode
from gzip import GzipFile

from methods import get_path_parent

import json, urllib2


class APIProvider(object):
    def __init__(self, payload):
        self.payload = payload

        node = self.get_matching_path(['owner', 'login'])
        self.owner = node['owner']['login'].lower()
        self.repo = node['name'].lower()

        node = self.get_matching_path(['number'])
        self.issue_number = node.get('number')

        node = self.get_matching_path(['labels'])
        self.labels = map(lambda obj: obj['name'].lower(), node.get('labels', []))

    def get_matching_path(self, matches):   # making the helper available for handlers
        return get_path_parent(self.payload, matches)

    def get_sender_and_creator(self):
        sender = self.payload['sender']['login'].lower()    # who triggered the payload
        node = self.get_matching_path(['user', 'login']) or {'user': {'login': ''}}
        creator = node['user']['login'].lower()     # (optional) creator of issue/pull
        return sender, creator

    # Per-repo configuration (FIXME: go for regex?)
    def get_matching_repos(self, repo_names):
        for name in repo_names:
            # Initially, assume that it's a wildcard match (for all owners and repos)
            watcher_owner, watcher_repo = self.owner, self.repo

            split = name.lower().split('/')
            if len(split) == 2:
                watcher_owner = split[0]
                # match for all repos owned by a particular owner
                watcher_repo = self.repo if split[1] == '*' else split[1]
            elif split[0] != '*':
                continue            # invalid format

            if watcher_owner == self.owner and watcher_repo == self.repo:
                yield name

    def get_labels(self):
        raise NotImplementedError

    def post_comment(self, comment):
        raise NotImplementedError


class GithubAPIProvider(APIProvider):
    base_url = 'https://api.github.com/repos/'
    comments_post_url = base_url + '%s/%s/issues/%s/comments'
    labels_get_url = base_url + "%s/%s/issues/%s/labels"

    def __init__(self, payload, user, token):
        self.user = user
        self.token = token
        super(GithubAPIProvider, self).__init__(payload)

    def request(self, method, url, data=None):
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

    def get_labels(self):
        url = self.labels_get_url % (self.owner, self.repo, self.issue_number)
        if self.labels:
            return self.labels

        _header, body = self.request('GET', url)
        self.labels = map(lambda obj: obj['name'].lower(), json.loads(body))
        return self.labels

    def post_comment(self, comment):
        url = self.comments_post_url % (self.owner, self.repo, self.issue_number)
        try:
            self.request('POST', url, {'body': comment})
        except urllib2.HTTPError as err:
            if err.code != 201:
                raise err
