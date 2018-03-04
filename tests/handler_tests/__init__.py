from highfive.api_provider.interface import APIProvider
from highfive.runner import config as config_overridable
from highfive.runner.config import Configuration
from highfive import event_handlers
from json_cleaner import JsonCleaner

import json
import os
import os.path as path
import sys


class TestAPIProvider(APIProvider):
    '''
    Mock APIProvider for unit testing the handlers. During tests, the initial rules and expectations
    are stored, and this object is passed to the handlers. Later, the actual values are evaluated
    against the expected values.
    '''
    # Since we're going for getting/setting attributes, we should make sure
    # that we're using the same names for both initial/expected values (in JSON)
    # and the class variables
    def __init__(self, config, payload, initial, expected):
        super(TestAPIProvider, self).__init__(config, payload)
        self.expected = expected

        for key, val in expected.iteritems():
            # Initialize with a new instance of the expected value's type
            # (not the value itself!), so that we can check those values
            # again after executing a handler
            val_type = type(val)
            instance = None if val == None else val_type()
            setattr(self, key, instance)

        for key, val in initial.items():    # set/override the values
            setattr(self, key, val)

    def get_branch_head(self, owner, repo, branch=None):
        return self.head['%s/%s' % (owner, repo)]

    def edit_comment(self, id_, comment):
        self.comments[str(id_)] = comment

    def set_assignees(self, assignees=[]):
        self.assignees = assignees

    def get_labels(self):
        return self.labels

    def replace_labels(self, labels=[]):
        self.labels = labels

    def post_comment(self, comment):
        self.comments.append(comment.decode('utf-8'))

    def get_diff(self):
        return self.diff

    def get_contributors(self):
        return map(lambda name: name.lower(), self.contributors)

    def get_page_content(self, path):
        with open(path) as fd:
            return fd.read()

    def rand_choice(self, values):
        return values[0]    # so that the results are consistent

    def get_screenshots_for_build(self, build_url):
        return self.image_data

    def post_image_to_imgur(self, base64_data):
        # Passing empty data imitates failure to upload to Imgur
        if base64_data:
            return 'https://imgur.com/' + '-'.join(base64_data.lower().split())

    def evaluate(self):
        for key, expected_val in self.expected.iteritems():
            value = getattr(self, key)
            assert value == expected_val, \
                "Expected value: %s\nValue found: %s" % (expected_val, value)


def run():
    tests, failed, dirty = 0, 0, 0
    name, args = sys.argv[0], sys.argv[1:]
    overwrite = os.getenv('CLEAN') is not None
    warn = not overwrite
    config = Configuration()
    config_overridable.read_file = lambda p: 'booya'

    tests_root = path.dirname(path.abspath(__file__))
    repo_root = path.dirname(path.dirname(tests_root))
    config_file = path.join(repo_root, 'highfive', 'config.json')
    with open(config_file, 'r') as fd:
        default_config = json.load(fd)

    config.initialize_defaults({
        'name': 'test-app',
        'pem_key': None,
        'secret': 'baz',
        'integration_id': 0,
        'collaborators': default_config['collaborators'],
        'database_url': 'foo',      # just to ignore dumping
    })

    event_handlers.load_handlers_using(config)

    for event in config.enabled_events:
        for handler_path, handler in event_handlers.get_handlers_for(event, cached=True):
            local_path = handler_path.split(os.sep)[2:]
            test_payloads_dir = path.join(tests_root, *local_path)

            # Every handler should have at least one test
            if not path.exists(test_payloads_dir):
                print 'Test not found for handler in %s' % os.sep.join(local_path)
                failed += 1
                continue

            for test in os.listdir(test_payloads_dir):
                test_path = os.path.join(test_payloads_dir, test)
                test_path_display = path.join(*test_path.split(os.sep)[-3:])
                # Test is a "JSON" "file"
                if not (path.isfile(test_path) and test_path.endswith('.json')):
                    continue

                with open(test_path, 'r') as fd:
                    test_data = json.load(fd)

                initial, expected = test_data['initial'], test_data['expected']
                initial_vals = initial if isinstance(initial, list) else [initial]
                expected_vals = expected if isinstance(expected, list) else [expected]

                wrapper = JsonCleaner({'payload': test_data['payload']})
                for (initial, expected) in zip(initial_vals, expected_vals):
                    api = TestAPIProvider(config, wrapper.json['payload'], initial, expected)
                    handler(api).handle_payload()
                    tests += 1

                    try:
                        api.evaluate()
                    except AssertionError as err:
                        print '\nError while testing %r with payload %r:\n%s' % \
                              (path.join(*local_path), test_path_display, err)
                        failed += 1

                cleaned = wrapper.clean(warn=warn)
                if warn and wrapper.unused:
                    print '%s has %d unused node(s)' % (test_path_display, wrapper.unused)
                    dirty += 1
                elif wrapper.unused and overwrite:
                    test_data['payload'] = cleaned['payload']
                    with open(test_path, 'w') as fd:
                        contents = json.dumps(test_data, indent=2)
                        trimmed = map(lambda line: line.rstrip() + '\n', contents.splitlines())
                        fd.writelines(trimmed)

                    print 'Rewrote', test_path_display

    print '\nRan %d test(s): %d error(s), %d file(s) dirty' % (tests, failed, dirty)

    if failed or dirty:
        if dirty:
            print 'Run `CLEAN=1 python %s` to cleanup the dirty file(s)' % name
        sys.exit(1)
