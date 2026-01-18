#!/usr/bin/env bash

sut_nodes=$(
	gcloud compute instances list \
		--zones=europe-west3-c \
		--format="csv(name,networkInterfaces[0].accessConfigs[0].natIP)" |
		grep sut-node |
		cut -d, -f 2 |
		sed 's/$/:6379/'
)

echo "SUT nodes:"
echo "$sut_nodes"

# This will only work if the SUT nodes were started in 'cluster' mode
valkey-cli \
	--no-auth-warning \
	--pass "csb-benchmark" \
	--cluster create $(echo $sut_nodes) \
	--cluster-replicas 0 \
	--cluster-yes
