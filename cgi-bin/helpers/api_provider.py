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
        self.comment = payload['comment']['body'].encode('utf-8') if payload.get('comment') else None

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

    def set_assignees(self, assignees):
        url = self.assignees_url % (self.owner, self.repo, self.issue_number)
        self._request('POST', url, {'assignees': assignees})

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

            match = None
            if headers.get('Link'):
                match = re.search(r'<(.*)>; rel="next".*<(.*)>; rel="last"',
                                  headers['Link'])
            if not match:
                break

            last_url = match.group(2)
            if url == last_url:
                break
            url = match.group(1)

        return contributors
