from helpers.api_provider import APIProvider
from helpers.methods import HANDLERS_DIR, get_handlers

import json, os, sys

TESTS_DIR = 'tests'


class TestAPIProvider(APIProvider):
    def __init__(self, payload, initial, expected):
        super(TestAPIProvider, self).__init__(payload)
        self.expected = expected

        for key, val in expected.items():
            # Initialize with a new instance of the value's type (not the value itself!)
            setattr(self, key, type(val)())

        for key, val in initial.items():
            setattr(self, key, val)

    def get_labels(self):
        return self.labels

    def post_comment(self, comment):
        self.comments.append(comment)

    def evaluate(self):
        for key, expect_val in self.expected.items():
            val = getattr(self, key)
            assert val == expect_val, \
                  "Value found '%s' != expected value '%s'" % (val, expect_val)


if __name__ == '__main__':
    tests, errors = 0, 0

    with open('config.json', 'r') as fd:
        config = json.load(fd)

    events = config.get('enabled_events', [])
    for path, handler in get_handlers(events):
        test_payloads_dir = TESTS_DIR + path.lstrip(HANDLERS_DIR)
        if not os.path.exists(test_payloads_dir):
            print 'Warning: Test not found for handler in %r' % path
            errors += 1
            continue

        for test in os.listdir(test_payloads_dir):
            tests += 1
            test_path = os.path.join(test_payloads_dir, test)
            with open(test_path, 'r') as fd:
                test_data = json.load(fd)

            initial, expected = test_data['initial'], test_data['expected']
            payload = test_data['payload']
            api = TestAPIProvider(payload, initial, expected)
            handler(api)

            try:
                api.evaluate()
            except AssertionError as err:
                print '\nError while testing %r with payload %r: \n%s\n' % (path, test_path, err)
                errors += 1

    if errors:
        print '\nRan %d test(s): %d error(s) found!' % (tests, errors)
        sys.exit(1)
