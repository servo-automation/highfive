from highfive.api_provider.interface import APIProvider
from highfive.event_handlers import EventHandler

from api_provider_tests import create_config
from unittest import TestCase


class TestHandler(EventHandler):
    called = False
    def on_issue_open(self):
        self.called = True


class EventHandlerTests(TestCase):
    def test_handler_ignore_inactive(self):
        '''
        The payload doesn't have "action" keyword. If it's been properly handled, then
        we'll get an error and this test will fail.
        '''

        api = APIProvider(config=create_config(), payload={})
        config = { 'active': False }
        handler = TestHandler(api, config)
        handler.handle_payload()

    def test_handler_ignore_disallowed_repo(self):
        '''
        If "allowed_repos" are specified in the per-handler config, then that's checked
        against the payload, and if it doesn't match, then the payload is ignored. If it doesn't
        ignore, then we hit the error on "action", and this test will fail.
        '''

        api = APIProvider(config=create_config(), payload={})
        config = {}
        api.owner, api.repo = 'foo', 'bar'
        config['active'] = True
        config['allowed_repos'] = ['baz/.*']
        handler = EventHandler(api, config)
        handler.handle_payload()

    def test_handler_allowed_repo(self):
        '''
        If the payload comes from somewhere that matches a pattern in "allowed_repos", then the
        method corresponding to the action is called.
        '''

        api = APIProvider(config=create_config(), payload={ 'action': 'opened' })
        config = {}
        api.owner, api.repo = 'foo', 'bar'
        config['active'] = True
        config['allowed_repos'] = ['foo/.*']
        handler = TestHandler(api, config)
        handler.handle_payload()
        self.assertTrue(handler.called)
