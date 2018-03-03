from ... import EventHandler

import re

class ServoMetadataChecker(EventHandler):
    '''
    Servo-specific handler to post warnings when PR diff has files added to WPT directory
    without metadata.
    '''

    def on_issue_open(self):
        if not (self.api.is_pull):
            return

        paths = list(self.api.get_changed_files())
        metadata_dirs = ['tests/wpt/metadata', 'tests/wpt/mozilla/meta']
        ignored = ['.ini', 'MANIFEST.json', 'mozilla-sync']
        offending_dirs = set()

        for path in paths:
            if '.' in path and not any(re.search(f, path) for f in ignored):
                offending_dirs |= set(d for d in metadata_dirs if re.search(d, path))

        if offending_dirs:
            message = self.config['message'].format(offending_dirs=self.join_names(offending_dirs))
            self.api.post_warning(message)


handler = ServoMetadataChecker
