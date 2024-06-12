#!/bin/sh

set -ex

ipfs dag import /webui.car

ipfs bootstrap rm all