
def check_lines(api, config):
    repos = config.get('repos')
    pr = api.payload.get('pull_request')
    if not (repos and pr and api.payload.get('action') == 'opened'):
        return

    repo_config = api.get_matches_from_config(repos)
    matches = repo_config.items()
    lines = api.get_added_lines()

    # FIXME: Change this to regex?
    messages = [msg for line in lines for match, msg in matches if match in line]

    if messages:
        lines = '\n'.join(map(lambda line: ' * %s' % line, messages))
        comment = ':warning: **Warning!** :warning:\n\n%s' % lines
        api.post_comment(comment)


methods = [check_lines]
