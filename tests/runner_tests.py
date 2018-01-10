from highfive.runner import Configuration, Runner

from unittest import TestCase

import json

class RunnerTests(TestCase):
    def create_runner(self):
        config = Configuration()
        config.config['secret'] = 'foobar'
        config.config['integration_id'] = '999'
        runner = Runner(config)
        return runner

    def test_runner_init(self):
        runner = self.create_runner()
        self.assertEqual(runner.secret, 'foobar')
        self.assertEqual(runner.integration_id, 999)

    def test_runner_payload_verify(self):
        runner = self.create_runner()
        raw_data = json.dumps({'foo': 'bar'})
        signature = 'sha1=08511d260b8322ad739a3f34665855ba6044366e'
        code, payload = runner.verify_payload(signature, raw_data)
        self.assertTrue(code is None)
        self.assertTrue(payload is not None)

    def test_runner_invalid_payload(self):
        runner = self.create_runner()
        code, payload = runner.verify_payload('', '')
        self.assertTrue(payload is None)
        self.assertEqual(code, 400)

    def test_runner_invalid_sign(self):
        runner = self.create_runner()
        raw_data = json.dumps({'foo': 'bar'})
        signature = 'sha1=0xdeadbeef'
        code, payload = runner.verify_payload(signature, raw_data)
        self.assertTrue(payload is None)
        self.assertEqual(code, 403)
