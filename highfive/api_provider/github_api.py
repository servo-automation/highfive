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
