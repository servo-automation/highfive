from ... import EventHandler

import re

class CommitDiffChecker(EventHandler):
    '''
    This checks the PR diff for content and file patterns and posts "warning" comments correspondingly.
    An useful feature is that paths and test paths can be specified in the config, and if some file
    in a path is changed and the test path isn't affected, then this handler adds a warning.
    '''

    messages = set()    # so that we filter duplicates

    def _get_messages(self, lines, matches):
        for line in lines:
            for match, msg in matches.iteritems():
                if re.search(match, line):
                    self.messages.add(msg)

    def _check_tests(self, config, paths):
        no_tests = []
        test_check = config.get('test_check', [])

        for check in test_check:
            name, modify_path, test_paths = check['name'], check['path'], check['test_paths']
            for path in paths:
                if re.search(modify_path, path):
                    found = filter(lambda path: any(re.search(p, path) for p in test_paths), paths)
                    if not found:
                        no_tests.append(name)
                    break

        if no_tests:
            self.messages.add(config["no_test_comment"].format(names=self.join_names(no_tests)))

    def on_issue_open(self):
        if not (self.api.is_pull):
            return

        self.messages = set()
        config = self.get_matched_subconfig() or {}

        matches = config.get('content', {})
        lines = self.api.get_added_lines()
        self._get_messages(lines, matches)

        matches = config.get('files', {})
        paths = list(self.api.get_changed_files())
        self._get_messages(paths, matches)

        self._check_tests(config, paths)

        if self.messages:
            lines = '\n'.join(map(lambda line: ' * %s' % line, self.messages))
            self.api.post_warning(lines)


handler = CommitDiffChecker
