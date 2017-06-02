from helpers.api_provider import APIProvider
from helpers.database import Database
from helpers.json_cleanup import JsonCleaner
from helpers.methods import AVAILABLE_EVENTS, CONFIG, HANDLERS_DIR, ROOT
from helpers.methods import get_handlers, get_logger, get_path_parent

import itertools, json, logging, os, sys

TESTS_DIR = os.path.join(ROOT, 'tests')


class TestDatabase(Database):
    def __init__(self, db_dict):
        self.stuff = db_dict

    def get_obj(self, _id, key):
        return self.stuff.get(key, {})

    def remove_obj(self, _id, key):
        self.stuff.pop(key)

    def write_obj(self, data, _id, key):
        self.stuff[key] = data


class TestAPIProvider(APIProvider):
    # Since we're going for getting/setting attributes, we should make sure
    # that we're using the same names for both initial/expected values (in JSON)
    # and the class variables
    def __init__(self, name, payload, initial, expected):
        super(TestAPIProvider, self).__init__(name, payload)
        self.logger = get_logger(__name__)
        self.expected = expected
        self.db = {}

        for key, val in expected.items():
            # Initialize with a new instance of the expected value's type
            # (not the value itself!), so that we can check those values
            # again after running a handler
            val_type = type(val)
            instance = None if val == None else val_type()
            setattr(self, key, instance)

        for key, val in initial.items():    # set/override the values
            setattr(self, key, val)

        if hasattr(self, 'db'):
            self.db = TestDatabase(self.db)

    def get_matching_path(self, matches, node=None):
        node = self.payload if node is None else self.payload[node]
        return get_path_parent(node, matches, get_obj=lambda marker: marker._node)

    def rand_choice(self, values):
        return values[0]    # so that the results are consistent

    def get_labels(self):
        return self.labels

    def replace_labels(self, labels=[]):
        self.labels = labels

    def post_comment(self, comment):
        self.comments.append(comment.decode('utf-8'))

    def get_diff(self):
        return self.diff

    def set_assignees(self, assignees):
        # Github API offers setting multiple assignees. In an issue's payload,
        # we can find both "assignee" and "assignees". The latter is an array,
        # while the former is a value, which is the first value from the array.
        # Hence, it shouldn't make any difference.
        self.assignee = assignees

    def get_page_content(self, path):
        with open(os.path.join(ROOT, path)) as fd:
            return fd.read()

    def close_issue(self):
        self.closed = True

    def evaluate(self):
        for key, expect_val in self.expected.items():
            val = getattr(self, key)
            if key == 'db':
                val = val.stuff

            assert val == expect_val, \
                "Expected value: %s\nValue found: %s" % (expect_val, val)


if __name__ == '__main__':
    tests, failed, dirty = 0, 0, 0
    name, args = sys.argv[0], sys.argv[1:]
    overwrite = True if 'write' in args else False
    warn = not overwrite
    logging.basicConfig(level=logging.ERROR)

    # The "tests" directory should have the same structure as that of the "handlers"
    for event in AVAILABLE_EVENTS:
        handler_gen = itertools.chain(enumerate(get_handlers(event)),
                                      enumerate(get_handlers(event, sync=True)))
        prev = -1
        is_sync = False
        for i, (path, handler) in handler_gen:
            is_sync = True if i < prev else is_sync     # hack for finding sync handlers
            prev = i

            local_path = path.split(os.sep)[len(HANDLERS_DIR.split(os.sep)):]
            handler_name = os.path.basename(path)
            test_payloads_dir = os.path.join(TESTS_DIR, *local_path)
            if not os.path.exists(test_payloads_dir):   # a handler should have at least one test
                print 'Test not found for handler in %s' % os.sep.join(local_path)
                failed += 1
                continue

            for test in os.listdir(test_payloads_dir):
                test_path = os.path.join(test_payloads_dir, test)
                if not os.path.isfile(test_path):
                    continue

                with open(test_path, 'r') as fd:
                    test_data = json.load(fd)

                initial, expected = test_data['initial'], test_data['expected']
                initial_vals = initial if isinstance(initial, list) else [initial]
                expected_vals = expected if isinstance(expected, list) else [expected]

                wrapper = JsonCleaner({'payload': test_data['payload']})
                for (initial, expected) in zip(initial_vals, expected_vals):
                    api = TestAPIProvider(CONFIG['name'], wrapper.json['payload'], initial, expected)
                    if is_sync:
                        handler(api, api.db, 1, handler_name)
                    else:
                        handler(api)
                    tests += 1

                    try:
                        api.evaluate()
                    except AssertionError as err:
                        print '\nError while testing %r with payload %r:\n%s' % \
                              (os.sep.join(local_path),
                               os.sep.join(test_path.split(os.sep)[len(HANDLERS_DIR.split(os.sep)):]), err)
                        failed += 1

                cleaned = wrapper.clean(warn)   # final cleanup for unused nodes in JSON
                if warn and wrapper.unused:
                    print 'The file %s has %d unused nodes!' % (test_path, wrapper.unused)
                    dirty += 1
                elif wrapper.unused and overwrite:
                    test_data['payload'] = cleaned['payload']
                    with open(test_path, 'w') as fd:
                        contents = json.dumps(test_data, indent=2)
                        trimmed = map(lambda line: line.rstrip() + '\n', contents.splitlines())
                        fd.writelines(trimmed)

                    print 'Rewrote %s' % test_path

    print '\nRan %d test(s): %d error(s), %d file(s) dirty' % (tests, failed, dirty)

    if failed or dirty:
        if dirty:
            print 'Run `python %s write` to cleanup the dirty files' % name
        sys.exit(1)
