from ....event_handlers import EventHandler

import re

class GithubPermalinkFinder(EventHandler):
    '''Ensures that the Github URLs in comments have been expanded to their canonical forms.'''

    def on_new_comment(self):
        comment = self.api.comment
        matches = re.findall('github.com/(.*?)/(.*?)/(?:(blob|tree))/master', comment)

        for match in matches:
            owner, repo = match[0], match[1]
            comment_id = self.api.payload['comment']['id']
            head = self.api.get_branch_head(owner=owner, repo=repo)
            comment = re.sub(r'(github.com/%s/%s/(?:(blob|tree)))/master' % (owner, repo),
                             r'\1/%s' % head, comment)

        if matches:
            self.api.logger.debug('Replacing links to master branch for comment ID: %s...', comment_id)
            self.api.edit_comment(comment_id, comment)


handler = GithubPermalinkFinder
