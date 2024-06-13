#!/bin/sh

set -ex

ipfs config --json Swarm.AddrFilters []

ipfs bootstrap add {root_node_addr}

rm /container-init.d/ipfs-node-init.sh