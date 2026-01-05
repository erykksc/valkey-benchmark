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
cloud services enable compute.googleapis.com

cd terraform
# initialize terraform
terraform init
# see the deployment plan
terraform plan
# initialize terraform
terraform apply # `add --auto-approve` to not get prompted
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

### Docker vs Bare Metal

I've decided to go with deploying valkey inside docker containers, as it is a realistic way of deploying it.
For future research one could look into running it on bare metal to check the difference.

### OS Type

I've chosen Google's COS, as it is optimized for running containers and has minimal amount of other services running, reducing the impact on the benchmark.
For the client node I've went with Debian, as I don't need so many optimizations and it comes with some basic tools added.
