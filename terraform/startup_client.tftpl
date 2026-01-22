#!/bin/bash
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get upgrade -y
# Same dependencies as in Dockerfile.build
apt-get install -y \
	build-essential \
	make \
	gcc \
	git \
	pkg-config \
	libssl-dev \
	wget \
	btop \
	tmux \
	tcl \
	procps

# Install valkey binaries
cd /usr/local/bin
wget -O valkey-cli https://storage.googleapis.com/${valkey_binaries_bucket}/valkey-cli
wget -O valkey-benchmark https://storage.googleapis.com/${valkey_binaries_bucket}/valkey-benchmark
wget -O my-valkey-benchmark https://storage.googleapis.com/${valkey_binaries_bucket}/my-valkey-benchmark
chmod +x valkey-cli valkey-benchmark my-valkey-benchmark

touch /done
