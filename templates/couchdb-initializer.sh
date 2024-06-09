#!/bin/bash

sleep 15
curl -X PUT http://{couchdb_admin_username}:{couchdb_admin_password}@couchdb:{couchdb_port}/_users 
curl -X PUT http://{couchdb_admin_username}:{couchdb_admin_password}@couchdb:{couchdb_port}/_replicator 
curl -X PUT http://{couchdb_admin_username}:{couchdb_admin_password}@couchdb:{couchdb_port}/_global_changes