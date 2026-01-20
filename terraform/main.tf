provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

resource "google_compute_network" "vpc_network" {
  name                    = "valkey-benchmark-network"
  auto_create_subnetworks = true
}

resource "google_compute_firewall" "all" {
  name = "allow-all"
  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  network       = google_compute_network.vpc_network.id
  source_ranges = ["0.0.0.0/0"]
}

resource "google_storage_bucket" "valkey_binaries" {
  name          = "valkey-binaries-${var.project_id}"
  location      = var.region
  force_destroy = true
}

resource "google_storage_bucket_iam_member" "public_access" {
  bucket = google_storage_bucket.valkey_binaries.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

locals {
  binaries = toset([
    "valkey-server",
    "valkey-cli",
    "valkey-benchmark",
    "my-valkey-benchmark",
  ])
}

resource "google_storage_bucket_object" "valkey_binaries" {
  for_each = local.binaries
  name     = each.key
  bucket   = google_storage_bucket.valkey_binaries.name
  source   = "../bin/${each.key}"

  depends_on = [google_storage_bucket.valkey_binaries]
}

resource "google_compute_instance" "sut_nodes" {
  name         = "valkey-sut-node-${count.index + 1}"
  count        = var.sut_instance_count
  machine_type = var.sut_machine_type


  boot_disk {
    initialize_params {
      size  = var.boot_disk_size_gb
      image = var.instance_image_sut
    }
  }
  metadata_startup_script = templatefile("startup_sut.sh", {
    deployment_mode        = var.deployment_mode
    valkey_binaries_bucket = google_storage_bucket.valkey_binaries.name
  })


  network_interface {
    network = google_compute_network.vpc_network.id
    access_config {
      # Necessary for external IP address
    }
  }
}

resource "google_compute_instance" "client" {
  name         = "valkey-client-node"
  machine_type = var.client_machine_type

  boot_disk {
    initialize_params {
      image = var.instance_image_client
      size  = var.boot_disk_size_gb
    }
  }
  metadata_startup_script = templatefile("startup_client.sh", {
    valkey_binaries_bucket = google_storage_bucket.valkey_binaries.name
  })


  network_interface {
    network = google_compute_network.vpc_network.id
    access_config {
      # Necessary for external IP address
    }
  }
}

output "client_external_ip" {
  description = "The external IP address of the client instance."
  value       = google_compute_instance.client.network_interface[0].access_config[0].nat_ip
}

output "sut_external_ips" {
  description = "The external IP addresses of the SUT instances."
  value       = [for instance in google_compute_instance.sut_nodes : instance.network_interface[0].access_config[0].nat_ip]
}

output "deployment_mode" {
  description = "The deployment mode for Valkey."
  value       = var.deployment_mode
}
