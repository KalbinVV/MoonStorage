#!/bin/sh

set -ex

ipfs dag import /webui.car

ipfs bootstrap rm all

ipfs bootstrap add {root_node_addr}