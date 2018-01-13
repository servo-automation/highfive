from ..runner.config import get_logger
from ..runner.request import request_with_requests

import random

class APIProvider(object):
    '''
    The interface used by `GithubAPIProvider` object to take actions based on
    the incoming payload. API provider objects are tied to payloads.

    Once the runner receives a payload, an API provider object is created and
    sent to all handlers (through the installation and synchronization managers).
    This object is supposed to provide encapsulation for commonly used payload
    attributes and methods, so that the handlers don't have to worry about
    extracting them every time.
    '''

    imgur_post_url = 'https://api.imgur.com/3/image'

    def __init__(self, config, payload):
        self.name = config['name']
        self.config = config
        self.payload = payload
        self.logger = get_logger(__name__)

        self.is_pull = None
        self.pull_url = None
        self.is_open = None
        self.creator = None
        self.last_updated = None
        self.number = None

        if payload.get('pull_request'):
            self.is_pull = True
            self.pull_url = payload['pull_request']['url']
            self.creator = payload['pull_request']['user']['login']
            self.is_open = payload['pull_request']['state'] == 'open'
            self.last_updated = payload['pull_request'].get('updated_at')
            self.number = payload['pull_request']['number']
        elif payload.get('issue'):
            self.is_pull = False
            self.creator = payload['issue']['user']['login']
            self.is_open = payload['issue']['state'] == 'open'
            self.last_updated = payload['issue'].get('updated_at')
            self.number = payload['issue']['number']

    def post_image_to_imgur(self, base64_data, json_request=request_with_requests):
        '''
        If the client ID is present in configuration, then this method can be used to
        upload base64-encoded image data (anonymously) to Imgur and returns the permalink.
        '''

        if self.config['imgur_client_id'] is None:
            self.logger.error('Imgur client ID has not been set!')
            return

        headers = {'Authorization': 'Client-ID %s' % self.config['imgur_client_id']}

        resp = json_request('POST', self.imgur_post_url,
                            data={'image': base64_data},
                            headers=headers)
        if resp.code != 200:
            self.logger.error('Error posting image to Imgur! Response: %s' % resp.data)
            return

        if not resp.is_json():
            self.logger.error('Cannot parse response from Imgur! Response: %s' % resp.data)
            return

        return resp.data['data']['link']
