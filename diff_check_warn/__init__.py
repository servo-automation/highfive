import re


def check_diff(api, config):
    repos = config.get('repos')
    pr = api.payload.get('pull_request')
    if not (repos and pr and api.payload.get('action') == 'opened'):
        return

    messages = set()    # so that we filter duplicates
    repo_config = api.get_matches_from_config(repos)

    def get_messages(lines, matches):
        for line in lines:
            for match, msg in matches.items():
                if re.search(match, line):
                    messages.update([msg])

    matches = repo_config['content']
    lines = api.get_added_lines()
    get_messages(lines, matches)

    matches = repo_config['files']
    paths = api.get_changed_files()
    get_messages(paths, matches)

    if messages:
        lines = '\n'.join(map(lambda line: ' * %s' % line, messages))
        comment = ':warning: **Warning!** :warning:\n\n%s' % lines
        api.post_comment(comment)


methods = [check_diff]
