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

    def __init__(self, config, payload, api_json_request):
        super(GithubAPIProvider, self).__init__(config, payload)
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
