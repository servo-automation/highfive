from ... import EventHandler
from time import sleep

import re

class LabelResponder(EventHandler):
    '''Adds/removes labels whenever a PR is opened/updated/merged/conflicted.'''

    labels_to_add = []
    labels_to_remove = []

    def _is_valid_payload(self):
        self.label_actions = self.get_matched_subconfig()
        return self.label_actions and self.api.is_pull

    def _on_open_or_update(self):
        if not self._is_valid_payload():
            return

        is_mergeable = self.api.payload['pull_request']['mergeable']
        # It's a bool. If it's None, then the data isn't available yet!
        while is_mergeable is None:
            sleep(2)                    # wait for Github to determine mergeability
            pull = self.api.get_pull()
            is_mergeable = pull['mergeable']

        self.labels_to_add += self.label_actions.get('open_or_update_add', [])
        self.labels_to_remove += self.label_actions.get('open_or_update_remove', [])

        conflict_add = self.label_actions.get('merge_conflict_add', [])
        conflict_remove = self.label_actions.get('merge_conflict_remove', [])
        self.labels_to_add += conflict_remove if is_mergeable else conflict_add
        self.labels_to_remove += conflict_add if is_mergeable else conflict_remove

    def on_issue_open(self):
        self._on_open_or_update()
        self.api.update_labels(add=self.labels_to_add, remove=self.labels_to_remove)

    def on_pr_update(self):
        self._on_open_or_update()
        self.api.update_labels(add=self.labels_to_add, remove=self.labels_to_remove)

    def on_issue_closed(self):
        if not self._is_valid_payload():
            return

        if self.api.payload['pull_request'].get('merged'):
            self.labels_to_add += self.label_actions.get('merge_add', [])
            self.labels_to_remove += self.label_actions.get('merge_remove', [])

        self.api.update_labels(add=self.labels_to_add, remove=self.labels_to_remove)

    def reset(self):
        self.labels_to_add = []
        self.labels_to_remove = []


handler = LabelResponder
