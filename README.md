## Steps to run

```bash
# create a project named 'valkey-benchmark' in Google Cloud Console
# NOTE: you can use a different project name, but then change it in the `./terraform/variables.tf`
#       or adapt all terraform commands with runtime argument

# login to gcloud cli
gcloud auth login
# set the project
gcloud config set project valkey-benchmark
# enable compute service
gcloud services enable compute.googleapis.com
gcloud auth application-default login

# destroy the previous deployment and deploy the cloud resources again
# NOTE: you can see the individual steps in `./mise.toml` file if you don't want to use `mise`
mise run redeploy

# wait for the system to deploy fully


# connect the SUT nodes into a cluster if deploying in a cluster mode (default deployment is single node)
./setup-cluster.sh

# check if the cluster is healty
./check-cluster.sh
# NOTE: for single node use `./check-single.sh`

# TODO: implement
./run-benchmark.sh

# TODO: implement
./get-results.sh

# destroy the deployed infrastructure
cd terraform
terraform destroy --auto-approve
```

## Decisions

### VM Type (Machine Type)

> Machine Type is the gcloud terminology for a VM size/type

I've chosen `t2d-standard` as it should "deliver leading price-performance for scale-out workloads" according to [Google](https://cloud.google.com/blog/products/compute/google-cloud-introduces-tau-vms)[Read on 04.01.2026].
The Machine Type provides fully physical cores, which should provide much more predictible performance and better L3 cache isolation per vCPU.
Additionally it doesn't support/use vCPU bursting, so that the results will be consistent.
Furthermore it always uses `Always AMD EPYC (Milan)` processor type, compared to other VM types such as `e2-standard` ones.

As I benchmark pure in-memory througput (Persistance will be OFF), I've decided not to use a VM with SSD attached.

For the load-generator I've chosen

#### Benchmark runs

For single node I would like to run:

| Machine Type    | Price/Month |
| --------------- | ----------- |
| t2d-standard-1  | 45$/month   |
| t2d-standard-2  | 85$/month   |
| t2d-standard-4  | 164$/month  |
| t2d-standard-8  | 323$/month  |
| t2d-standard-16 | 641/month   |
| t2d-standard-32 | 1,276/month |
| t2d-standard-48 | 1,912/month |
| t2d-standard-64 | 2,389/month |

For cluster:
3x t2d-standard-1 ~= 134$/month

### Docker vs Bare Metal

I've decided to go with deploying valkey inside docker containers, as it is a realistic way of deploying it.
For future research one could look into running it on bare metal to check the difference.

### OS Type

I've chosen Google's COS, as it is optimized for running containers and has minimal amount of other services running, reducing the impact on the benchmark.
For the client node I've went with Debian, as I don't need so many optimizations and it comes with some basic tools added.

### Cluster Size

Note that the minimal cluster that works as expected must contain at least three primary nodes. For deployment, we strongly recommend a six-node cluster, with three primaries and three replicas.

### Valkey Version

I've decided to test bleeding edge with version 9.0.1, instead of provided by package maintainers version 8

### Data-generation

I'm using Zipf Distribution (exponent:1.1, offset:1.0) as it is resembles realistic traffic, some keys/data are retrieved much more often than some other ones.
I'm using a seeded random data generator so that the data-generator produces the same data each time.
I'm using keys of length 7(prefix)+16(uuid), this is an attempt to generate realistic key lengths.
Variable key sizes could be further area of research (look for paper that already did that).

### Workload

Starts with 10% GET and 90% SET and linearliy shifts to 90% GET and 10% SET

### TODO

1. Pin the Process: Use taskset to lock the Valkey process to a single physical core to prevent the OS from moving it around, which ruins benchmark consistency.
2. Titanium Advantage: C4 uses Google's "Titanium" offload engine. This moves networking and storage tasks to dedicated hardware, leaving the CPU 100% free for your code.
