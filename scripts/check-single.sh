#!/usr/bin/env bash

sut_nodes=$(
	gcloud compute instances list \
		--zones=europe-west3-c \
		--format="csv(name,networkInterfaces[0].accessConfigs[0].natIP)" |
		grep sut-node |
		cut -d, -f 2
)

first_node=$(echo "$sut_nodes" | head -n 1)

if gcloud compute ssh valkey-sut-node-1 --zone=europe-west3-c --command "ls /valkey-installed >/dev/null 2>&1"; then
	echo "Valkey was reported to be installed on the sut node"
else
	echo "The file /valkey-installed does NOT exist on sut node. Wait until deployment finishes."
	exit 1
fi

if gcloud compute ssh valkey-client-node --zone=europe-west3-c --command "ls /done >/dev/null 2>&1"; then
	echo "SUT client has reported done with the installation"
else
	echo "The file /done does NOT exist on the sut client node. Wait until deployment finishes."
	exit 1
fi

command_args=(
	valkey-cli
	--no-auth-warning
	--pass 'csb-benchmark'
	-h "$first_node"
	info
)

gcloud compute ssh valkey-client-node --zone=europe-west3-c --command="${command_args[*]}"
