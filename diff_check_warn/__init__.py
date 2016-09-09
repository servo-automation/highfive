import re


def _check_tests(api, repo_config, paths):
    no_tests = []
    test_check = repo_config.get('test_check', [])

    for check in test_check:
        name, modify_path, test_paths = check['name'], check['path'], check['test_paths']
        for path in paths:
            if re.search(modify_path, path):
                found = filter(lambda path: any(re.search(p, path) for p in test_paths), paths)
                if not found:
                    no_tests.append(name)
                break

    message = ('These commits modify the %s code, but no tests have been modified. '
               'Please consider updating the tests appropriately.')
    if no_tests:
        return message % api.shared.join_names(no_tests)


# Servo-specific WPT metadata checker
def _check_metadata(api, paths):
    msg = ('This pull request adds file(s) to `%s` without the `.ini` extension. '
           'Please consider removing the file(s)!')

    metadata_dirs = ['tests/wpt/metadata', 'tests/wpt/mozilla/meta']
    ignored = ['.ini', 'MANIFEST.json', 'mozilla-sync']
    offending_file_dirs = set()

    for path in paths:
        if '.' in path and not any(re.search(f, path) for f in ignored):
            offending_file_dirs |= set(d for d in metadata_dirs if re.search(d, path))

    if offending_file_dirs:
        return msg % api.shared.join_names(offending_file_dirs)


# define and append the repo-specific handlers here
REPO_SPECIFIC_HANDLERS = {
    "servo/servo": {
        "lines": [
            # content-checking methods
        ],
        "paths": [
            # path-checking methods
            _check_metadata
        ]
    },
}


def check_diff(api, config):
    repos = config.get('repos')
    pr = api.payload.get('pull_request')
    if not (pr and api.payload.get('action') == 'opened'):
        return

    messages = set()    # so that we filter duplicates
    repo_config = api.get_matches_from_config(repos)

    def get_messages(lines, matches):
        for line in lines:
            for match, msg in matches.items():
                if re.search(match, line):
                    messages.update([msg])

    matches = repo_config.get('content', {})
    lines = api.get_added_lines()
    get_messages(lines, matches)

    matches = repo_config.get('files', {})
    paths = list(api.get_changed_files())
    get_messages(paths, matches)

    test_check_result = _check_tests(api, repo_config, paths)
    if test_check_result:
        messages.update([test_check_result])

    # Run the repo-specific handlers (if any)
    handlers = api.get_matches_from_config(REPO_SPECIFIC_HANDLERS)
    for name, methods in handlers.items():
        for method in methods:
            _input = locals().get(name)
            result = method(api, _input)
            if result:
                messages.update([result])

    if messages:
        lines = '\n'.join(map(lambda line: ' * %s' % line, messages))
        comment = ':warning: **Warning!** :warning:\n\n%s' % lines
        api.post_comment(comment)


methods = [check_diff]
