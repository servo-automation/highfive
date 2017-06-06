from copy import deepcopy
from methods import get_path_parent, get_logger

import contextlib, random, re, urllib2


class APIProvider(object):
    def __init__(self, name, payload):
        self.name = name
        self.payload = payload
        self.is_pull = payload.get('pull_request') != None
        self.pull_url = payload['pull_request']['url'] if self.is_pull else None
        self.diff = None

        node = self.get_matching_path(['owner', 'login'])
        self.owner = node['owner']['login'].lower() if node.get('owner') else None
        self.repo = node['name'].lower() if node.get('name') else None

        node = self.get_matching_path(['assignee'])
        self.assignee = node['assignee']['login'].lower() if node.get('assignee') else None

        self.sender = payload['sender']['login'].lower() if payload.get('sender') else None
        self.current_label = payload['label']['name'].lower() if payload.get('label') else None

        node = self.get_matching_path(['number'])
        num = node.get('number')
        if num is not None:
            num = str(num)          # Having an integer seems to cause trouble at certain times.
        self.issue_number = num

        # Github labels are unique and case-insensitive (which is really helpful!)
        node = self.get_matching_path(['labels'])
        self.labels = map(lambda obj: obj['name'].lower(), node.get('labels', []))

        self.is_open = None
        self.creator = None
        self.last_updated = None

        if self.is_pull:
            self.creator = self.payload['pull_request']['user']['login']
            self.is_open = self.payload['pull_request']['state'] == 'open'
            self.last_updated = self.payload['pull_request'].get('updated_at')
        elif self.payload.get('issue'):
            self.creator = self.payload['issue']['user']['login']
            self.is_open = self.payload['issue']['state'] == 'open'
            self.last_updated = self.payload['issue'].get('updated_at')

    def get_matching_path(self, matches):       # making the helper available for handlers
        return get_path_parent(self.payload, matches)

    # Per-repo configuration
    def get_matches_from_config(self, config):
        if not (self.owner and self.repo):
            assert not self.payload     # This happens only when we call sync handlers
            return config

        result = None
        string = '%s/%s' % (self.owner, self.repo)
        for pattern in config:
            pat_lower = pattern.lower()
            if re.search(pat_lower, string):
                if not result:
                    result = deepcopy(config[pattern])
                elif isinstance(result, list):
                    result.extend(config[pattern])
                elif isinstance(result, dict):
                    result.update(config[pattern])

        return result

    def rand_choice(self, values):
        return random.choice(values)

    def get_labels(self):
        raise NotImplementedError

    def replace_labels(self, labels=[]):
        raise NotImplementedError

    # FIXME: This doesn't seem to work as expected. Verify it?
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

    def close_issue(self):
        raise NotImplementedError

    def is_from_self(self):
        return self.name in self.sender

    def get_branch_head(self, branch):
        raise NotImplementedError

    def edit_comment(self, _id, comment):
        raise NotImplementedError


class GithubAPIProvider(APIProvider):
    base_url = 'https://api.github.com/repos/%s/%s'
    issue_url = base_url + '/issues/%s'
    branch_url = base_url + '/branches/%s'
    comments_post_url = issue_url + '/comments'
    comments_patch_url = base_url + '/issues/comments/%s'
    labels_url = issue_url + '/labels'
    assignees_url = issue_url + '/assignees'
    diff_url = 'https://github.com/%s/%s/pull/%s.diff'

    def __init__(self, name, payload, request_method):
        super(GithubAPIProvider, self).__init__(name, payload)
        self._request = request_method
        self.logger = get_logger(__name__)

    # self-helpers

    def _handle_labels(self, method, labels=[]):
        url = self.labels_url % (self.owner, self.repo, self.issue_number)
        data = self._request(method, url, labels)
        labels = map(lambda obj: obj['name'].lower(), data)
        return labels

    # handler helpers

    def get_labels(self):       # FIXME: This always makes a request if the labels are empty
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

    def close_issue(self):
        url = self.issue_url % (self.owner, self.repo, self.issue_number)
        self._request('PATCH', url, {'state': 'closed'})

    def edit_comment(self, _id, comment):
        url = self.comments_patch_url % (self.owner, self.repo, _id)
        self._request('PATCH', url, {'body': comment})

    def get_branch_head(self, owner=None, repo=None, branch='master'):
        owner = self.owner if owner is None else owner
        repo = self.repo if repo is None else repo
        url = self.branch_url % (owner, repo, branch)
        is_auth = owner == self.owner and repo == self.repo
        return self._request('GET', url, auth=is_auth)['commit']['sha']
