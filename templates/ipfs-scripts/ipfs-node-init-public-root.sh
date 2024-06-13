#!/bin/sh

set -ex

ipfs config --json Swarm.AddrFilters []

rm /container-init.d/ipfs-node-init.sh