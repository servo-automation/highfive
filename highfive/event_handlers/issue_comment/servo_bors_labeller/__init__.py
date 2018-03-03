from ... import EventHandler

import re

class ServoBorsLabeller(EventHandler):
    '''
    Rust and Servo organizations have 'bors' for tthe "test before merge" flow.
    This handler checks bors comments for specific patterns and updates the labels accordingly.
    '''

    def on_new_comment(self):
        if self.api.sender != self.config["bors_name"]:
            return

        self.logger.debug("Checking comment from bors...")
        for action, subconfig in self.config.get("actions", {}).iteritems():
            if not any(re.search(pat, self.api.comment) for pat in subconfig.get("comment_patterns", [])):
                continue

            labels_to_add = subconfig.get("labels_to_add", [])
            labels_to_remove = subconfig.get("labels_to_remove", [])
            self.api.update_labels(add=labels_to_add, remove=labels_to_remove)
            return


handler = ServoBorsLabeller
