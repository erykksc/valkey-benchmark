#!/bin/bash

apt-get update
apt-get upgrade -y

# Add iptables rules to allow Valkey traffic
iptables -A INPUT -p tcp --dport 6379 -j ACCEPT  # For client connections
iptables -A INPUT -p tcp --dport 16379 -j ACCEPT # For the Valkey cluster bus

# Install valkey
cd /usr/local/bin
wget -O valkey-server https://storage.googleapis.com/${valkey_binaries_bucket}/valkey-server
chmod +x valkey-server
touch /valkey-installed

# Required by valkey
sysctl vm.overcommit_memory=1

# Calculate the cores to use, equivalent to min(max(nproc/4, 1), 4)
NUM_CORES=$(nproc)
QUARTER_CORES=$((NUM_CORES / 4))
MAX_VAL=$((QUARTER_CORES > 1 ? QUARTER_CORES : 1))
RESULT=$((MAX_VAL < 4 ? MAX_VAL : 4))

# NOTE: ${deployment_mode} is a template variable from terraform's templatefile()
if [[ "${deployment_mode}" == "cluster" ]]; then
  echo "Starting Valkey in cluster mode"

  valkey-server \
    --cluster-enabled yes \
    --cluster-config-file nodes.conf \
    --cluster-node-timeout 5000 \
    --io-threads "$RESULT" \
    --requirepass "csb-benchmark" \
    --appendonly yes

elif [[ "${deployment_mode}" == "single" ]]; then
  echo "Starting Valkey in single mode"

  valkey-server \
    --io-threads "$RESULT" \
    --requirepass "csb-benchmark" \
    --appendonly yes

else
  echo "ERROR: Unknown deployment_mode '${deployment_mode}'"
  exit 1
fi
