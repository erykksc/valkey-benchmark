#!/usr/bin/env bash

set -e

sut_nodes_newline=$(
	gcloud compute instances list \
		--zones=europe-west3-c \
		--format="csv(name,networkInterfaces[0].accessConfigs[0].natIP)" |
		grep sut-node |
		cut -d, -f 2 |
		sed 's/$/:6379/'
)

NODE_COUNT=$(echo "$sut_nodes_newline" | wc -l)

sut_nodes_comma=$(echo "$sut_nodes_newline" | paste -sd, -)

echo "SUT nodes (comma-separated):"
echo "$sut_nodes_comma"

echo "Fetching hardware info from sut-node-1"
REMOTE_VARS=$(gcloud compute ssh valkey-sut-node-1 --zone=europe-west3-c --command="
	  REMOTE_CPU=\$(lscpu | grep 'Model name' | awk -F: '{print \$2}' | xargs | awk '{print \$1\"-\"\$2\"-\"\$3}');
      REMOTE_CORES=\$(nproc);
      REMOTE_RAM=\$(free -h | awk '/^Mem:/ {print \$2}' | sed 's/\./p/');
      echo \"CPU='\${REMOTE_CPU}'\";
      echo \"CORES='\${REMOTE_CORES}'\";
      echo \"RAM='\${REMOTE_RAM}'\";
")

eval "$REMOTE_VARS"
echo "Hardware Info of SUT nodes"
echo "  CPU: $CPU"
echo "  Cores: $CORES"
echo "  RAM: $RAM"
echo "  NODE_COUNT: $NODE_COUNT"

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M")
FILENAME="results/${NODE_COUNT}x${CPU}_${CORES}cores_${RAM}_${TIMESTAMP}.csv"
echo "Results filename: $FILENAME"

command_args=(my-valkey-benchmark
	-target-addr "$sut_nodes_comma"
	-password 'csb-benchmark'
	-total-keys 100000000
	-concurrency 256
	-pool-size-mb 100
	-duration 20m
	-output "$FILENAME"
)

# create results directory
gcloud compute ssh valkey-client-node --zone=europe-west3-c --command="mkdir -p results"
gcloud compute ssh valkey-client-node --zone=europe-west3-c --command="${command_args[*]}"
