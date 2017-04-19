from StringIO import StringIO
from gzip import GzipFile
from jose import jwt

from methods import Shared, get_path_parent

import contextlib, json, re, requests, time, urllib2


class APIProvider(object):
    def __init__(self, payload):
        self.payload = payload
        self.shared = Shared()
        self.pull_url = payload['pull_request']['url'] if payload.get('pull_request') else None
        self.diff = None

        node = self.get_matching_path(['owner', 'login'])
        self.owner = node.get('owner', {'login': ''})['login'].lower()
        self.repo = node.get('name', '').lower()

        # payload sender and (optional) creator of issue/pull/comment
        self.sender = payload['sender']['login'].lower() if payload.get('sender') else None
        node = self.get_matching_path(['user', 'login']) or {'user': {'login': ''}}
        self.creator = node['user']['login'].lower()    # (optional) creator of issue/pull

        node = self.get_matching_path(['number'])
        self.issue_number = node.get('number')

        # Github labels are unique and case-insensitive (which is really helpful!)
        node = self.get_matching_path(['labels'])
        self.labels = map(lambda obj: obj['name'].lower(), node.get('labels', []))

        node = self.get_matching_path(['issue', 'state'])
        self.is_open = node['issue']['state'] == 'open' if node else None

    def get_matching_path(self, matches):   # making the helper available for handlers
        return get_path_parent(self.payload, matches)

    # Per-repo configuration
    def get_matches_from_config(self, config):
        repo_config = {}
        string = '%s/%s' % (self.owner, self.repo)

        for pattern in config:
            pat_lower = pattern.lower()
            if re.search(pat_lower, string):
                for key, val in config[pattern].items():
                    if repo_config.get(key) and isinstance(val, list):
                        repo_config[key] += val
                    else:
                        # NOTE: This overrides the previous value (if any)
                        # Make sure that the matches in config file doesn't have such keys
                        repo_config[key] = val

        return repo_config

    def get_labels(self):
        raise NotImplementedError

    def replace_labels(self, labels=[]):
        raise NotImplementedError

    def update_labels(self, add=[], remove=[]):
        to_lower = lambda label: label.lower()      # str.lower doesn't work for unicode
        current_labels = set(map(to_lower, self.get_labels()))
        current_labels.update(map(to_lower, add))
        current_labels.difference_update(map(to_lower, remove))
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

    def get_changed_files(self):
        diff = self.get_diff()
        for line in diff.splitlines():
            # Get paths from a line like 'diff --git a/path/to/file b/path/to/file'
            if line.startswith('diff --git '):
                file_paths = filter(lambda p: p.startswith('a/') or p.startswith('b/'),
                                    line.split())
                file_paths = set(map(lambda p: p[2:], file_paths))
                for path in file_paths:
                    yield path      # yields only one item atmost!

    def post_comment(self, comment):
        raise NotImplementedError

    def set_assignees(self, assignees):
        raise NotImplementedError

    def get_page_content(self, path):
        raise NotImplementedError


class GithubAPIProvider(APIProvider):
    base_url = 'https://api.github.com/'
    issue_url = base_url + 'repos/%s/%s/issues/%s/'
    comments_post_url = issue_url + 'comments'
    labels_url = issue_url + 'labels'
    assignees_url = issue_url + 'assignees'
    diff_url = 'https://github.com/%s/%s/pull/%s.diff'
    installation_url = base_url + 'installations/%s/access_tokens'
    headers = {
        'Content-Type': 'application/json',
        # integration-specific header
        'Accept': 'application/vnd.github.machine-man-preview+json',
        'Accept-encoding': 'gzip'
    }

    def __init__(self, payload, pem_key, int_id):
        self.token = None
        self.pem = pem_key
        self.int_id = int_id
        super(GithubAPIProvider, self).__init__(payload)
        self._sync_token()

    # self-helpers

    # https://developer.github.com/early-access/integrations/authentication/#jwt-payload
    def _sync_token(self):      # FIXME: Sync only after the token expires
        since_epoch = int(time.time())
        auth_payload = {
            'iat': since_epoch,
            'exp': since_epoch + 600,       # 10 mins expiration for JWT
            'iss': self.int_id,
        }

        url = self.installation_url % self.payload['installation']['id']
        self.token = jwt.encode(auth_payload, self.pem, 'RS256')
        resp = self._request('POST', url, auth='Bearer')
        self.token = resp['token']      # installation token (expires in 1 hour)

    def _request(self, method, url, data=None, auth='token'):
        self.headers['Authorization'] = '%s %s' % (auth, self.token)
        data = json.dumps(data) if data is not None  else data
        req_method = getattr(requests, method.lower())
        print '%s: %s (data: %s)' % (method, url, data)
        resp = req_method(url, data=data, headers=self.headers)
        data, code = resp.text, resp.status_code

        if code < 200 or code >= 300:
            print 'Got a %s response: %r' % (code, data)
            raise Exception

        if resp.headers.get('Content-Encoding') == 'gzip':
            try:
                fd = GzipFile(fileobj=StringIO(data))
                data = fd.read()
            except IOError:
                pass
        try:
            return json.loads(data)
        except (TypeError, ValueError):         # stuff like 'diff' will be a string
            return data

    def _handle_labels(self, method, labels=[]):
        url = self.labels_url % (self.owner, self.repo, self.issue_number)
        data = self._request(method, url, labels)
        labels = map(lambda obj: obj['name'].lower(), data)
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
        return self._request('GET', self.pull_url)

    def get_diff(self):
        if self.diff:
            return self.diff

        url = self.diff_url % (self.owner, self.repo, self.issue_number)
        self.diff = self._request('GET', url)
        return self.diff

    def post_comment(self, comment):
        url = self.comments_post_url % (self.owner, self.repo, self.issue_number)
        self._request('POST', url, {'body': comment})

    def set_assignees(self, assignees):
        url = self.assignees_url % (self.owner, self.repo, self.issue_number)
        self._request('POST', url, {'assignees': assignees})

    def get_page_content(self, url):
        with contextlib.closing(urllib2.urlopen(url)) as fd:
            return fd.read()
