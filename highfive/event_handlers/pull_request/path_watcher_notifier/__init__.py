from ... import EventHandler

import re

class PathWatcherNotifier(EventHandler):
    '''Checks the paths in PR diff and notifies the watchers of those paths (if any).'''

    def on_issue_open(self):
        config = self.get_matched_subconfig()
        if not (config and self.api.is_pull):
            return

        mentions = {}
        for path in self.api.get_changed_files():
            for user, watched in config.iteritems():
                if user == self.api.creator:    # don't mention the creator
                    continue

                not_watched = filter(lambda p: p.startswith('-'), watched)
                not_watched = map(lambda p: p.lstrip('-'), not_watched)
                watched = filter(lambda p: not p.startswith('-'), watched)

                for watched_path in watched:
                    if path.startswith(watched_path):
                        if any(path.startswith(p) for p in not_watched):
                            continue

                        mentions.setdefault(user, [])
                        mentions[user].append(path)

        if not mentions:
            return

        message = [self.config['message_header']]
        for watcher, files in mentions.items():
            message.append(" * @{}: {}".format(watcher, ', '.join(files)))

        self.api.post_comment('\n'.join(message))


handler = PathWatcherNotifier
