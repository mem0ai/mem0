from typing import Dict, Optional, Union

import httpx


def build_http_client(http_client_proxies: Optional[Union[Dict, str]]) -> Optional[httpx.Client]:
    if not http_client_proxies:
        return None
    if isinstance(http_client_proxies, dict):
        return httpx.Client(
            mounts={scheme: httpx.HTTPTransport(proxy=url) for scheme, url in http_client_proxies.items()}
        )
    return httpx.Client(proxy=http_client_proxies)
