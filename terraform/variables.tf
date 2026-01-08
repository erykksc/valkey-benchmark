variable "project_id" {
  description = "The ID of the Google Cloud project."
  type        = string
  default     = "valkey-benchmark"
}

variable "region" {
  description = "The Google Cloud region to deploy resources in."
  type        = string
  default     = "europe-west3"
}

variable "zone" {
  description = "The Google Cloud zone to deploy resources in."
  type        = string
  default     = "europe-west3-c"
}

variable "sut_machine_type" {
  description = "The machine type for the SUT (Valkey) instance."
  type        = string
  default     = "t2d-standard-2"
}

variable "client_machine_type" {
  description = "The machine type for the client (load generator) instance."
  type        = string
  default     = "t2d-standard-2"
}

variable "boot_disk_size_gb" {
  description = "The size of the boot disk in GB."
  type        = number
  default     = 40
}

variable "instance_image_client" {
  description = "The OS image for the client VM instance."
  type        = string
  default     = "https://www.googleapis.com/compute/v1/projects/debian-cloud/global/images/debian-13-trixie-v20251209"
}

variable "instance_image_sut" {
  description = "The OS image for the SUT VM instances."
  type        = string
  default     = "https://www.googleapis.com/compute/v1/projects/debian-cloud/global/images/debian-13-trixie-v20251209"
}

variable "sut_instance_count" {
  description = "The number of SUT instances to create for the Valkey cluster."
  type        = number
  default     = 1
}

variable "deployment_mode" {
  description = "Deployment mode for Valkey: 'single' or 'cluster'."
  type        = string
  default     = "single"
  validation {
    condition     = contains(["single", "cluster"], var.deployment_mode)
    error_message = "Must be either 'single' or 'cluster'."
  }
}
