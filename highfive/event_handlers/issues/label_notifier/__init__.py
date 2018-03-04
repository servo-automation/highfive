from ... import EventHandler

class LabelNotifier(EventHandler):
    '''Notifies label watchers whenever their labels are added to an issue.'''

    def on_issue_label_add(self):
        config = self.get_matched_subconfig()
        if not config or self.api.is_pull:      # Ignore if it's a PR.
            return

        watchers_to_be_notified = []
        existing_labels = set(self.api.labels) - set([self.api.current_label])

        for user, labels in config.iteritems():
            user = user.lower()
            labels = map(lambda name: name.lower(), labels)
            # don't notify if the user's an author, or if the user is
            # the one who has triggered the label event
            if user == self.api.sender or user == self.api.creator:
                continue

            if any(label in existing_labels for label in labels):
                continue    # we've already notified the user

            # If we don't find any labels, then notify the user for any labelling event
            if (self.api.labels and not labels) or self.api.current_label in labels:
                watchers_to_be_notified.append(user)

        if watchers_to_be_notified:
            mentions = map(lambda name: '@%s' % name, watchers_to_be_notified)
            comment = 'cc %s' % ' '.join(mentions)
            self.api.post_comment(comment)


handler = LabelNotifier
