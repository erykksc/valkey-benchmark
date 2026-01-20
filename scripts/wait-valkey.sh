#!/usr/bin/env bash
#MISE description="Wait for deployed valkey and reutrn its' info once available"

DEPLOYMENT_MODE=$(cd terraform && terraform output -raw deployment_mode)

if [ "$DEPLOYMENT_MODE" == "cluster" ]; then
	until ./scripts/check-cluster.sh; do
		sleep 1
	done
elif [ "$DEPLOYMENT_MODE" == "single" ]; then
	until scripts/check-single.sh; do
		sleep 1
	done
else
	echo "ERROR: Running in unkown mode: $DEPLOYMENT_MODE"
	exit 1
fi
