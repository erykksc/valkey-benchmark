## Steps to run

> WARNING: All scripts from `scripts/` should be run from the root directory

You need to run the following steps only once (configure gcloud):

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
```

The following steps you need to run for each benchmark run:

```bash
# destroy the previous deployment and deploy the cloud resources again
# NOTE: you can see the individual steps in `./mise.toml` file if you don't want to use `mise`
# mise run redeploy # only for development purposes

# NOTE: for pruduction run
# deployment_mode can be either 'cluster' or 'single'
(
    set -e
    mise build
    cd terraform
    terraform apply \
        -var="client_machine_type=t2d-standard-32" \
        -var="sut_instance_count=24" \
        -var="sut_machine_type=t2d-standard-2" \
        -var="deployment_mode=cluster" \
        -var="io_threads=1" \
        --auto-approve
    cd ..
    ./scripts/wait-valkey.sh
    ./scripts/run-benchmark.sh
    cd terraform
    terraform destroy \
        -target="google_compute_instance.sut_nodes" \
        --auto-approve
    cd ..
    ./scripts/get-results.sh
    cd terraform
    terraform destroy --auto-approve
)

# wait for the system to deploy fully
# To approximate it you can use the script
./scripts/wait-valkey.sh

# connect the SUT nodes into a cluster if deploying in a cluster mode (default deployment is single node)
# NOTE: skip this step if benchmarking a single node deployment
./scripts/setup-cluster.sh

# check if the cluster is healty
./scripts/check-cluster.sh
# NOTE: for single node use `./check-single.sh`

./scripts/run-benchmark.sh

# run this step to remove the sut nodes as you download the results
# this way you can save some costs
(
    cd ./terraform
    terraform destroy \
        -target="google_compute_instance.sut_nodes" \
        --auto-approve

)

# collect results from the sut client onto local machine
./scripts/get-results.sh

# destroy the deployed infrastructure
cd terraform
terraform destroy --auto-approve
```

## Price calculation

To calculate the price of the VM instances in the cloud I've used the [gcosts](https://github.com/Cyclenerd/google-cloud-pricing-cost-calculator) tool.
This tools allows automatical price calculation, making it possible to compare the prices in the future.

This is a command to update the pricing.

```
curl -L "https://github.com/Cyclenerd/google-cloud-pricing-cost-calculator/raw/master/pricing.yml" \
     -o "pricing.yml"
```

Afterwards run this command to caluclate the prices of all benchmarked VM instance types combinations.

```
gcosts calc --dir ./cost-calc/ --pricing ./pricing.yml
```

## Decisions

### VM Type (Machine Type)

> Machine Type is the gcloud terminology for a VM size/type

I've chosen `t2d-standard` as it should "deliver leading price-performance for scale-out workloads" according to [Google](https://cloud.google.com/blog/products/compute/google-cloud-introduces-tau-vms)[Read on 04.01.2026].
The Machine Type provides fully physical cores, which should provide much more predictible performance and better L3 cache isolation per vCPU.
Additionally it doesn't support/use vCPU bursting, so that the results will be consistent.
Furthermore it always uses `Always AMD EPYC (Milan)` processor type, compared to other VM types such as `e2-standard` ones.

As I benchmark pure in-memory througput (Persistance will be OFF), I've decided not to use a VM with SSD attached.

For the load-generator I've chosen t2d-standard-48.
The 't2d-standard' has been chosen due to relative high amount of t2d-standard vcpu quoto on GCP.
Increasing quota was a struggle so we decided to use this one as it was fast enought and wasn't a bottlneck according to monitoring.

The network bandwidth of the load-generator node is 32 Gbps, which was below during the benchmark runs.

## OS Pricing

Some enterprises may decide to use RHEL Linux on their deployed services.
Initially we thought that it may be worth to include it in the price, as horizontal scaling requires more active instances.
However, the pricing of RHEL on GCP is per vcpu, making the comparison in our case not worth persuing, as we compare same vcpu count for horizontal and vertical scaling each time.

### Comparable Configurations

To answer the research question regarding cost-efficiency, we define specific comparison groups where the total monthly cost of the "Scale Up" (Single Node) scenario is roughly equivalent to the "Scale Out" (Cluster) scenario.

| Group                      | Single Node Config | Monthly Cost | Cluster Config       | Monthly Cost | Notes                                                          |
| :------------------------- | :----------------- | :----------- | :------------------- | :----------- | :------------------------------------------------------------- |
| **Budget Entry Level**     | `t2d-standard-1`   | ~$13.88      |                      |              | Cluster not achievable at this price                           |
| **Entry Level**            | `t2d-standard-4`   | ~$55.52      | `3x t2d-standard-1`  | ~$41.64      | Minimal cluster size (3 nodes)                                 |
| **Mid Range**              | `t2d-standard-16`  | ~$222.06     | `7x t2d-standard-2`  | ~$194.32     | 7-node cluster (3 primaries, 4 replicas/spare)                 |
| **High Performance**       | `t2d-standard-48`  | ~$666.18     | `24x t2d-standard-2` | ~$666.24     | **Exact Price Match.** 24-node cluster vs massive single node. |
| **High Performance (Alt)** | `t2d-standard-48`  | ~$666.18     | `48x t2d-standard-1` | ~$666.24     | **Exact Price Match.** 48 tiny nodes vs 1 massive node.        |

#### Benchmark runs

For single node I would like to run:

| Machine Type    | Price/Month | Commitment |
| --------------- | ----------- | ---------- |
| t2d-standard-1  | 13.88       | 3          |
| t2d-standard-2  | 27.76       | 3          |
| t2d-standard-4  | 55.52       | 3          |
| t2d-standard-8  | 111.03      | 3          |
| t2d-standard-16 | 222.06      | 3          |
| t2d-standard-32 | 444.12      | 3          |
| t2d-standard-48 | 666.18      | 3          |

For cluster:
3x t2d-standard-1 ~= 134$/month

[Here](https://gcloud-compute.com/instances.html) are the prices.

### Docker vs Bare Metal

I've decided to go with deploying valkey inside docker containers, as it is a realistic way of deploying it.
For future research one could look into running it on bare metal to check the difference.

### OS Type

I've chosen Google's COS, as it is optimized for running containers and has minimal amount of other services running, reducing the impact on the benchmark.
For the client node I've went with Debian, as I don't need so many optimizations and it comes with some basic tools added.

### IO-Threads

According to some benchmarks from the community, setting more io-threads than 8 provides diminishing returns:
https://riferrei.com/the-engineering-wisdom-behind-rediss-single-threaded-design/

This uses Amdahl's Law.

### Cluster Size

Note that the minimal cluster that works as expected must contain at least three primary nodes. For deployment, we strongly recommend a six-node cluster, with three primaries and three replicas.

### Valkey Version

I've decided to test bleeding edge with version 9.0.1, instead of provided by package maintainers version 8

### Data-generation

I'm using Zipf Distribution (exponent:1.1, offset:1.0) as it is resembles realistic traffic, some keys/data are retrieved much more often than some other ones.
I'm using a seeded random data generator so that the data-generator produces the same data each time.
I'm using keys of length 7(prefix)+16(Base64 Encoded UUID), this is an attempt to generate realistic key lengths.
Variable key sizes could be further area of research (look for paper that already did that).

### Workload

Starts with 10% GET and 90% SET and linearliy shifts to 90% GET and 10% SET

### TODO

1. Pin the Process: Use taskset to lock the Valkey process to a single physical core to prevent the OS from moving it around, which ruins benchmark consistency.
2. Titanium Advantage: C4 uses Google's "Titanium" offload engine. This moves networking and storage tasks to dedicated hardware, leaving the CPU 100% free for your code.
3. Calculate and decide on the key count to use
