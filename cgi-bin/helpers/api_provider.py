from copy import deepcopy
from methods import CONFIG, get_path_parent, get_logger

import random, re, requests


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
            # This happens only when we call sync handlers
            # (We later override owner and repo and call this again)
            assert not self.payload
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

    def create_issue(self, title, body, labels, assignees):
        raise NotImplementedError

    def close_issue(self):
        raise NotImplementedError

    def is_from_self(self):
        return self.name in self.sender

    def get_branch_head(self, branch):
        raise NotImplementedError

    def edit_comment(self, _id, comment):
        raise NotImplementedError

    def get_contributors(self):
        raise NotImplementedError

    def get_screenshots_for_build(self, url):
        raise NotImplementedError

    def post_image_to_imgur(self, base64_data):
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
    contributors_url = base_url + '/contributors?per_page=500'
    imgur_post_url = 'https://api.imgur.com/3/image'

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
        resp = requests.get(url)
        return resp.text

    def create_issue(self, title, body, labels=[], assignees=[]):
        url = self.base_url + '/issues'
        return self._request('POST', url, {
            "title": title,
            "assignees": assignees,
            "labels": labels,
            "body": body
        })

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

    # Recursively traverses through the paginated data to get contributors list.
    # It's forbidden to call this more than once in a session, since it will open
    # one of the gates to Tartarus, exposing our world to the Titans.
    def get_contributors(self):
        self.logger.debug('Updating contributors list...')
        contributors = []
        url = self.contributors_url % (self.owner, self.repo)

        while True:
            headers, data = self._request('GET', url, headers_required=True)
            contributors.extend(map(lambda v: v['login'], data))
            match = re.search(r'<(.*)>; rel="next".*<(.*)>; rel="last"',
                              headers['Link'])
            if not match:
                break

            last_url = match.group(2)
            if url == last_url:
                break
            url = match.group(1)

        return contributors

    # Other helper methods unrelated to the Github API.
    # (since they're unrelated, they can use `requests` module directly)

    def get_screenshots_for_build(self, build_url):
        url = CONFIG.get('servo_reftest_screenshot_endpoint')
        url.rstrip('/')
        url += '/?url=%s' % build_url   # FIXME: should probably url encode?
        resp = requests.get(url)
        if resp.status_code != 200:
            self.logger.error('Error requesting %s' % url)
            return

        try:
            return json.loads(resp.text)
        except (TypeError, ValueError):
            self.logger.debug('Cannot decode JSON data from %s' % url)

    def post_image_to_imgur(self, base64_data):
        if not CONFIG.get('imgur_client_id'):
            self.logger.error('Imgur client ID has not been set!')
            return

        headers = {'Authorization': 'Client-ID %s' % CONFIG['imgur_client_id']}
        resp = requests.post(self.imgur_post_url, data={'image': base64_data},
                             headers=headers)
        if resp.status_code != 200:
            self.logger.error('Error posting image to Imgur')
            return None

        try:
            data = json.loads(resp.text)
            return data['data']['link']
        except (TypeError, ValueError):
            self.logger.debug('Error parsing response from Imgur')
