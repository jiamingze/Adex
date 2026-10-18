"""Verify the public App gateway, rather than trusting a living tunnel process."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def gateway_ready(origin: str) -> bool:
    """The unauthenticated profile endpoint must return the App's JSON 401."""
    try:
        with urlopen(origin.rstrip('/') + '/api/v1/me', timeout=10):
            return False
    except HTTPError as error:
        if error.code != 401:
            return False
        try:
            return json.loads(error.read()).get('code') == 'UNAUTHENTICATED'
        except (ValueError, AttributeError):
            return False
    except (URLError, TimeoutError, OSError):
        return False
