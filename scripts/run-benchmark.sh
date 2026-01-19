#!/usr/bin/env bash

sut_nodes_newline=$(
	gcloud compute instances list \
		--zones=europe-west3-c \
		--format="csv(name,networkInterfaces[0].accessConfigs[0].natIP)" |
		grep sut-node |
		cut -d, -f 2 |
		sed 's/$/:6379/'
)

# Use `paste` to join all lines of the input with a comma
sut_nodes_comma=$(echo "$sut_nodes_newline" | paste -sd, -)

echo "SUT nodes (comma-separated):"
echo "$sut_nodes_comma"

command_args=(
	my-valkey-benchmark
	-target-addr "$sut_nodes_comma"
	-password 'csb-benchmark'
	-total-keys 1000000
	-concurrency 1024
	-pool-size 100
	-duration 20m
)

gcloud compute ssh valkey-client-node --zone=europe-west3-c --command="${command_args[*]}"
