#!/bin/sh

set -ex
ipfs bootstrap rm all

peer_id="`ipfs config Identity.PeerID`"

ipfs bootstrap add "/ip4/{ipfs_peer_id_addr}/tcp/4001/ipfs/$peer_id"
