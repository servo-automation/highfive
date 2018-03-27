from interface import APIProvider

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

    def __init__(self, config, payload, store, api_json_request):
        super(GithubAPIProvider, self).__init__(config, payload, store)
        self._request = api_json_request

    def get_branch_head(self, owner=None, repo=None, branch='master'):
        '''Get the latest revision of the given branch in a repo.'''

        owner = self.owner if owner is None else owner
        repo = self.repo if repo is None else repo
        url = self.branch_url % (owner, repo, branch)
        requires_auth = owner == self.owner and repo == self.repo
        return self._request('GET', url, auth=requires_auth)['commit']['sha']

    def edit_comment(self, id_, comment):
        '''Update the body of the comment associated with an ID.'''

        url = self.comments_patch_url % (self.owner, self.repo, id_)
        self._request('PATCH', url, {'body': comment})

    def set_assignees(self, assignees=[]):
        '''Set the given list of assignees to the associated issue/PR'''

        url = self.assignees_url % (self.owner, self.repo, self.number)
        self._request('POST', url, {'assignees': assignees})

    def get_labels(self):
        '''
        Fetches the labels for the issue/PR from which this payload was generated.
        This makes an API request only when the payload doesn't have any label information.
        Presently, the labels live only as long as the payload.
        '''
        if self.labels is not None:
            return self.labels

        self.labels = self._handle_labels('GET')
        return self.labels

    def replace_labels(self, labels=[]):
        '''
        Method to replace the labels in remote with the given list of labels.
        Clears all labels by default (i.e., empty list).
        '''

        self.labels = self._handle_labels('PUT', labels=labels)

    def post_comment(self, comment):
        '''Post a comment to the associated issue/PR.'''

        url = self.comments_post_url % (self.owner, self.repo, self.number)
        self._request('POST', url, {'body': comment})

    def get_diff(self):
        '''Get the diff for this pull request.'''

        if self.diff:
            return self.diff

        url = self.diff_url % (self.owner, self.repo, self.number)
        self.diff = self._request('GET', url)
        return self.diff

    def get_pull(self):
        '''Fetch the latest info for the pull request associated with this payload.'''

        return self._request('GET', self.pull_url)

    def fetch_contributors(self):
        '''Recursively traverses through the paginated data to get contributors list.'''

        contributors = []
        url = self.contributors_url % (self.owner, self.repo)

        while True:
            headers, data = self._request('GET', url, headers_required=True)
            contributors.extend(map(lambda v: v['login'].lower(), data))

            match = None
            if headers.get('Link'):
                match = re.search(r'<(.*)>; rel="next".*<(.*)>; rel="last"', headers['Link'])
            if not match:
                break

            last_url = match.group(2)
            if url == last_url:
                break
            url = match.group(1)

        return contributors

    def close_issue(self):
        '''Close the issue/PR associated with this payload.'''

        url = self.issue_url % (self.owner, self.repo, self.number)
        self._request('PATCH', url, {'state': 'closed'})


    def create_issue(self, title, body, labels=[], assignees=[]):
        '''Create an issue with the given title, body, labels and assignees.'''

        url = self.base_url + '/issues'
        return self._request('POST', url, {
            "title": title,
            "assignees": assignees,
            "labels": labels,
            "body": body
        })

    # Private methods

    def _handle_labels(self, method, labels=None):
        url = self.labels_url % (self.owner, self.repo, self.number)
        data = self._request(method=method, url=url, data=labels)
        labels = map(lambda obj: obj['name'].lower(), data)
        return labels
