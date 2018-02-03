from highfive.runner import Configuration, Runner
from highfive.runner.runner import HandlerError

from unittest import TestCase

import json

def create_runner():
    config = Configuration()
    config.name = 'test_app'
    config.secret = 'foobar'
    config.integration_id = '999'
    config.pem_key = 'baz'
    config.allowed_repos = ['servo']
    config.enabled_events = ['issues']
    runner = Runner(config)
    return runner

class RunnerTests(TestCase):
    def test_runner_init(self):
        runner = create_runner()
        self.assertEqual(runner.installations, {})
        getattr(runner, 'config')

    def test_runner_payload_verify(self):
        runner = create_runner()
        raw_data = json.dumps({'foo': 'bar'})
        signature = 'sha1=08511d260b8322ad739a3f34665855ba6044366e'
        code, payload = runner.verify_payload(signature, raw_data)
        self.assertTrue(code is None)
        self.assertTrue(payload is not None)

    def test_runner_invalid_payload(self):
        runner = create_runner()
        code, payload = runner.verify_payload('', '')
        self.assertTrue(payload is None)
        self.assertEqual(code, 400)

    def test_runner_invalid_sign(self):
        runner = create_runner()
        raw_data = json.dumps({'foo': 'bar'})
        signature = 'sha1=0xdeadbeef'
        code, payload = runner.verify_payload(signature, raw_data)
        self.assertTrue(payload is None)
        self.assertEqual(code, 403)

    def test_runner_payload_handling(self):
        runner = create_runner()
        payload = {
            'installation': {
                'id': 0
            },
            'repository': {
                'owner': {
                    'login': 'servo'
                },
                'name': 'highfive',
            }
        }

        self.assertEqual(len(runner.installations), 0)
        r = runner.handle_payload('installation_repositories', payload)
        self.assertTrue(r is HandlerError.NewInstallation)
        self.assertEqual(len(runner.installations), 0)
        r = runner.handle_payload('integration_installation_repositories', payload)
        self.assertTrue(r is HandlerError.NewInstallation)
        self.assertEqual(len(runner.installations), 0)

        # Disabled event from the same repo shouldn't affect the installation
        r = runner.handle_payload('status', payload)
        self.assertTrue(r is HandlerError.DisabledEvent)
        self.assertEqual(len(runner.installations), 1)
        runner.installations.clear()

        payload['sender'] = {'login': 'foo'}
        r = runner.handle_payload('issues', payload)
        self.assertTrue(r is None)      # successful handling
        self.assertFalse(runner.installations[0].queue.empty())     # payload pushed to queue

        # Payload from bot shouldn't affect the installation
        payload['sender'] = {'login': 'test_app'}
        r = runner.handle_payload('issues', payload)
        self.assertTrue(r is HandlerError.PayloadFromSelf)
        self.assertEqual(len(runner.installations), 1)
        runner.installations.clear()

        # However, payload from unregistered repo should remove installation (if it exists)
        payload['repository']['owner']['login'] = 'foobar'
        r = runner.handle_payload('issues', payload)
        self.assertEqual(len(runner.installations), 0)
        self.assertTrue(r is HandlerError.UnregisteredRepo)
