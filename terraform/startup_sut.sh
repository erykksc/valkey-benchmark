#!/bin/bash
export DEBIAN_FRONTEND=noninteractive

sudo apt update
sudo apt upgrade -y
# Same dependencies as in Dockerfile.build
sudo apt install -y \
  build-essential \
  make \
  gcc \
  git \
  pkg-config \
  libssl-dev \
  wget \
  tcl \
  procps

# Add iptables rules to allow Valkey traffic
iptables -A INPUT -p tcp --dport 6379 -j ACCEPT  # For client connections
iptables -A INPUT -p tcp --dport 16379 -j ACCEPT # For the Valkey cluster bus

# Required by valkey
sudo sysctl vm.overcommit_memory=1

# NOTE: ${deployment_mode} is a template syntax of terraform (templatefile)
if [[ "${DEPLOYMENT_MODE}" == "cluster" ]]; then
  echo "Starting Valkey in cluster mode"
  docker run -d --name valkey-node -v valkey-data:/data --net=host valkey/valkey:latest valkey-server \
    --port 6379 \
    --bind 0.0.0.0 \
    --cluster-enabled yes \
    --cluster-config-file /data/nodes.conf \
    --cluster-node-timeout 5000 \
    --appendonly yes
elif [[ "${DEPLOYMENT_MODE}" == "single" ]]; then
  echo "Starting Valkey in single mode"
  # TODO: write a proper docker run command
  docker run -d --name valkey-node -v valkey-data:/data --net=host valkey/valkey:latest valkey-server \
    --port 6379 \
    --bind 0.0.0.0 \
    --cluster-enabled yes \
    --cluster-config-file /data/nodes.conf \
    --cluster-node-timeout 5000 \
    --appendonly yes
else
  echo "ERROR: Unknown deployment_mode '${deployment_mode}'"
  exit 1
fi
