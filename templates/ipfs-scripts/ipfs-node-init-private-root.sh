#!/bin/sh

set -ex

ipfs dag import /webui.car

ipfs bootstrap rm all

ipfs config --json Swarm.AddrFilters []

rm /container-init.d/ipfs-node-init.sh