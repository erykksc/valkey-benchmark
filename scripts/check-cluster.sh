#!/usr/bin/env bash

sut_nodes=$(
	gcloud compute instances list \
		--zones=us-west1-c \
		--format="csv(name,networkInterfaces[0].accessConfigs[0].natIP)" |
		grep sut-node |
		cut -d, -f 2 |
		sed 's/$/:6379/'
)

first_node=$(echo "$sut_nodes" | head -n 1)

command_args=(
	valkey-cli
	--no-auth-warning
	--pass 'csb-benchmark'
	--cluster
	check "$first_node"
)

gcloud compute ssh valkey-client-node --zone=us-west1-c --command="${command_args[*]}"
