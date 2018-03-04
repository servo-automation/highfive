from ... import EventHandler

class ReviewerAssigner(EventHandler):
    '''
    This takes care of assigning a pull request to a reviewer (if they don't already exist).
    If a review request exists in the PR body, then it assigns them, or it falls back to
    reviewer rotation (when a reviewer is chosen based on the issue number). In the end, it pings
    the reviewer and welcomes the contributor (if it's a newcomer).
    '''

    def on_issue_open(self):
        reviewers = self.get_matches_from_config(self.api.config.collaborators)
        if not (reviewers and self.api.is_pull):
            return

        # If the PR already has an assignee, then don't try to assign one
        if self.api.assignee:
            return

        chosen_ones = self.find_reviewers(self.api.payload['pull_request']['body'])
        if not chosen_ones:    # go for reviewer rotation
            reviewers = filter(lambda name: name.lower() != self.api.creator, reviewers)
            if not reviewers:
                return

            chosen_ones = [reviewers[int(self.api.number) % len(reviewers)]]

        self.api.set_assignees(chosen_ones)
        config = self.get_matched_subconfig()
        if not config:
            return

        first = [chosen_ones[0]]
        rest = map(lambda s: '@' + s, chosen_ones[1:])
        mention = self.join_names(first + rest)
        comment = self.api.rand_choice(config['reviewer_msg']).format(reviewer=mention)
        self.api.post_comment(comment)

        foss_folks = self.api.get_contributors()
        if self.api.creator not in foss_folks:
            msg = self.api.rand_choice(config['newcomer_welcome_msg']).format(reviewer=mention)
            self.api.post_comment(msg)


handler = ReviewerAssigner
