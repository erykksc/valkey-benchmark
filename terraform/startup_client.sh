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

# Required by valkey
sudo sysctl vm.overcommit_memory=1

touch /done
