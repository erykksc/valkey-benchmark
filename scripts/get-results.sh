#!/usr/bin/env bash

gcloud compute scp \
	--zone us-west1-c \
	--recurse \
	--compress \
	valkey-client-node:~/results .
