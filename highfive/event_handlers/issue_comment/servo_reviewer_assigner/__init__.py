from ... import EventHandler

import re

class ServoReviewerAssigner(EventHandler):
    '''
    Follows Mozila's conventions for assigning reviewers from comments.

     - If the comment matches [prefix in configuration] followed by "r=[comma-separated usernames]",
       then the handler assigns those usernames.
     - Or, if the comment matches [prefix in configuration] followed by "r+", then the handler
       assigns the author of the comment.
     - Or, if the comment has a review request (like "r? @username"), then it assigns the
       requested reviewer.
    '''

    def _get_approver(self):
        prefix_regex = self.config.get("comment_prefix", '')
        approval_regex = prefix_regex + r'r([\+=])([a-zA-Z0-9\-,\+]*)'
        approval = re.search(approval_regex, self.api.comment)

        if approval:
            if approval.group(1) == '=':    # "r=foo" or "r=foo,bar"
                reviewer = approval.group(2)
                return reviewer
            return self.api.sender      # fall back and assign the approver

    def on_new_comment(self):
        reviewers = self._get_approver()
        if reviewers:
            self.logger.info('Setting reviewers:', reviewers)
            self.api.set_assignees(reviewers.split(','))
            return

        reviewers = self.find_reviewers(self.api.comment)   # find reviewers from review requests
        if reviewers:
            self.logger.info('Setting requested reviewers:', reviewers)
            self.api.set_assignees(reviewers)


handler = ServoReviewerAssigner
