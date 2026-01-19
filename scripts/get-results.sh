#!/usr/bin/env bash

gcloud compute scp \
	--zone europe-west3-c \
	--recurse \
	--compress \
	valkey-client-node:~/results .
