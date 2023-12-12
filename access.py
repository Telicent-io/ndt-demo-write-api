import requests

pass_through_headers = [
    "x-amzn-oidc-data",
    'x-amzn-oidc-accesstoken',
    "x-amzn-oidc-identity",
    "Authorization"
]

def get_headers(headers):
    forward_headers = {}
    for header in pass_through_headers:
        hv = headers.get(header)
        if hv is not None: 
            forward_headers[header] = hv
    return forward_headers

class AccessClient():
    def __init__(self, connection_string: str, dev_mode: bool):
        self.connection_string = connection_string
        self.dev = dev_mode
        
    def get_user_details(self, headers):
        if self.dev:
            return {"username": "Test User1", "user_id": "1234-5678-99ab-cdef"}
        res = requests.get(f"{self.connection_string}/user-info/self", headers=get_headers(headers))
        res.raise_for_status()
        if res.status_code == 200: 
            return res.json()
        

