from highfive.runner.config import read_file, Configuration

from unittest import TestCase

import json
import os


class ConfigurationTests(TestCase):
    def test_config_load(self):
        '''Test loading configuration from JSON'''

        config = Configuration()
        config_dict = {
            'integration_id': 2,
            'name': None,
            'pem_key': __file__,    # load this file (just for testing)
            'dump_path': os.path.dirname(__file__),
            'secret': 'foobar'
        }

        raw_config = json.dumps(config_dict)
        config.load_from_string(raw_config)
        test_contents = read_file(__file__)

        self.assertEqual(config.pem_key, test_contents)
        self.assertEqual(config.dump_path, 'tests')
        self.assertEqual(config.integration_id, 2)
        self.assertEqual(config.name, None)
        self.assertEqual(config.secret, 'foobar')

        # Check uninitialized defaults
        self.assertEqual(config.imgur_client_id, None)
        self.assertEqual(config.enabled_events,
                         ['issue_comment', 'issues', 'pull_request'])
        self.assertEqual(config.allowed_repos, [])
        self.assertEqual(config.collaborators, {})

    def test_config_env_replace(self):
        '''Test appropriate env variable substitution in configuration'''

        config = Configuration()
        os.environ['PEM_KEY'] = __file__
        config_dict = {
            'name': None,
            'integration_id': 0,
            'secret': 'ENV::SECRET',
            'bar': 'ENV::SECRET',
            'pem_key': 'ENV::PEM_KEY',
            # If `database_url` was initialized, then `dump_path` shouldn't be checked
            'database_url': 'something'
        }

        try:
            config.load_from_string(json.dumps(config_dict))
            assert False, 'SECRET is missing in environment, but no error was raised'
        except KeyError:
            os.environ['SECRET'] = 'foobar'

        test_contents = read_file(__file__)
        raw_config = json.dumps(config_dict)
        config.load_from_string(raw_config)
        self.assertEqual(config.pem_key, test_contents)
        self.assertEqual(config.secret, 'foobar')
        self.assertEqual(config.bar, 'foobar')      # multiple occurrences
