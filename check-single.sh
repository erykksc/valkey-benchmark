#!/usr/bin/env bash

sut_nodes=$(
	gcloud compute instances list \
		--zones=europe-west3-c \
		--format="csv(name,networkInterfaces[0].accessConfigs[0].natIP)" |
		grep sut-node |
		cut -d, -f 2
)

first_node=$(echo "$sut_nodes" | head -n 1)

valkey-cli --no-auth-warning \
	--pass "csb-benchmark" \
	-h "$first_node" \
	info server
