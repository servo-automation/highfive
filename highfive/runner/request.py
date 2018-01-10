import json
import requests

class Response(object):
    ''' The response object that should be returned by all "requesting" functions.'''

    def __init__(self, data, code=200, headers={}):
        self.code = code
        self.headers = headers
        self.data = data


def request_with_requests(method, url, data=None, headers={}):
    '''
    Make a request with the `requests` module to the given `url`
    with the given `method`, (optional) `data` and `headers`
    '''

    data = json.dumps(data) if data is not None else data
    req_method = getattr(requests, method.lower())  # hack for getting function
    resp = req_method(url, data=data, headers=headers)
    data = resp.text

    try:
        data = json.loads(data)
    except Exception:
        pass

    return Response(
        data=data,
        code=resp.status_code,
        headers=resp.headers
    )
