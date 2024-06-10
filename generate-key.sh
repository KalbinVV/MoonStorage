#!/bin/bash

(echo '/key/swarm/psk/1.0.0/\n/base16/' ; head -c 32 /dev/urandom | od -t x1 -A none - | tr -d '\n '; echo '') > ./swarm.key
