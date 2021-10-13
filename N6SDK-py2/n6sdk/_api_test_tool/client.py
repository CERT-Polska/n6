# Copyright (c) 2015-2021 NASK. All rights reserved.

import os.path
import json

import requests
import requests.exceptions

from n6sdk._api_test_tool.validator_exceptions import (
    APIClientException,
    APIValidatorException,
)


class APIClient(object):
    ''' Class for handling connection and requests to API '''

    _session = None
    _response = None
    _cert = None

    def __init__(self, cert_path=None, key_path=None, user=None, password=None, verify=False):
        self._session = requests.Session()
        if cert_path:
            self.set_certificate(cert_path, key_path)
        if user and password:
            self._session.auth = (user, password)
        self._verify = verify

    def set_certificate(self, cert_path, key_path):
        if cert_path and not os.path.isfile(cert_path):
            raise APIValidatorException("Certificate file not found")
        if key_path:
            if not os.path.isfile(key_path):
                raise APIValidatorException("Certificate key file not found")
        if cert_path and key_path:
            self._cert = (cert_path, key_path)
        else:
            self._cert = cert_path

    def get_stream(self, url, params=None):
        message = None
        code = None
        try:
            self._response = self._session.get(url, stream=True, cert=self._cert, verify=self._verify)
            self._response.raise_for_status()
        except requests.exceptions.SSLError as ssl_error:
            message = "SSL Certificate verification failed."
            exception = ssl_error
        except requests.exceptions.HTTPError as http_error:
            message = "HTTP error."
            exception = '{} (`{}`)'.format(
                http_error, self._response.content.replace('\n', ' ').strip())
            code = self._response.status_code
        except requests.exceptions.Timeout as timeout_error:
            message = "Connection timeout."
            exception = timeout_error
        except requests.exceptions.RequestException as req_error:
            message = "Connection failed due to unknown problems."
            exception = req_error
        if message:
            exc = APIClientException("{} {}".format(message, exception))
            exc.code = code
            raise exc
        if self._response and self._response.status_code == requests.codes.ok:
            for line in self._response.iter_lines(4096):
                if line:
                    yield json.loads(line)

    def status(self):
        if self._response:
            return self._response.status_code
