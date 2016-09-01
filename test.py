from helpers.api_provider import APIProvider
from helpers.json_cleanup import JsonCleaner
from helpers.methods import HANDLERS_DIR, get_handlers, get_path_parent

import json, os, sys

TESTS_DIR = 'tests'


class TestAPIProvider(APIProvider):
    def __init__(self, payload, initial, expected):
        super(TestAPIProvider, self).__init__(payload)
        self.expected = expected

        for key, val in expected.items():
            # Initialize with a new instance of the expected value's type
            # (not the value itself!), so that we can check those values
            # again after running a handler
            setattr(self, key, type(val)())

        for key, val in initial.items():    # set/override the values
            setattr(self, key, val)

    def get_matching_path(self, matches):
        return get_path_parent(self.payload, matches, get_obj=lambda marker: marker._node)

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
    tests, failed, dirty = (0,) * 3
    name, args = sys.argv[0], sys.argv[1:]
    overwrite = True if 'write' in args else False
    warn = not overwrite

    with open('config.json', 'r') as fd:
        config = json.load(fd)

    # The "tests" directory should have the same structure as that of the "handlers"
    events = config.get('enabled_events', [])
    for path, handler in get_handlers(events):
        test_payloads_dir = TESTS_DIR + path.lstrip(HANDLERS_DIR)
        if not os.path.exists(test_payloads_dir):   # a handler should have at least one test
            print 'Test not found for handler in %r' % test_payloads_dir
            failed += 1
            continue

        for test in os.listdir(test_payloads_dir):
            tests += 1
            test_path = os.path.join(test_payloads_dir, test)
            with open(test_path, 'r') as fd:
                test_data = json.load(fd)

            initial, expected = test_data['initial'], test_data['expected']
            wrapper = JsonCleaner({'payload': test_data['payload']})
            api = TestAPIProvider(wrapper.json['payload'], initial, expected)
            handler(api)

            try:
                api.evaluate()
            except AssertionError as err:
                print '\nError while testing %r with payload %r: \n%s' % (path, test_path, err)
                failed += 1

            cleaned = wrapper.clean(warn)   # final cleanup for unused nodes in JSON
            if warn and wrapper.unused:
                print 'The file %r has %d unused nodes!' % (test_path, wrapper.unused)
                dirty += 1
            elif overwrite:
                test_data['payload'] = cleaned['payload']
                with open(test_path, 'w') as fd:
                    json.dump(test_data, fd, indent=2)
                print 'Rewrote the JSON file: %r' % test_path

    print '\nRan %d test(s): %d error(s), %d files dirty' % (tests, failed, dirty)

    if failed or dirty:
        if dirty:
            print 'Run `python %s write` to cleanup the dirty files' % name
        sys.exit(1)
