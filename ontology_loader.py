
import json
import os
import requests
from urllib.parse import quote

with open('ies4.ttl') as file:
    data = file.read()
    headers = {'Content-Type': 'text/turtle;charset=utf-8'}
    r = requests.post('http://localhost:3030/ontology/data?default', data=data, headers=headers)
print("IES loaded")

