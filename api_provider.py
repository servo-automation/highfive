from base64 import standard_b64encode as b64_encode
from gzip import GzipFile
from helpers import get_matching_path_parent

import json, urllib2


class GithubAPIProvider(object):
    base_url = 'https://api.github.com/repos/'
    comments_post_url = base_url + '%s/%s/issues/%s/comments'

    def __init__(self, payload, user, token):
        self.user = user
        self.token = token
        self.payload = payload
        node = get_matching_path_parent(payload, ['owner', 'login'])
        self.owner = node['owner']['login']
        self.repo = node['name']
        node = get_matching_path_parent(payload, ['number'])
        self.issue_number = node.get('number')

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

    def post_comment(self, comment):
        url = self.comments_post_url % (self.owner, self.repo, self.issue_number)
        try:
            self.request('POST', url, {'body': comment})
        except urllib2.HTTPError as err:
            if err.code != 201:
                raise err
