provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

### NETWORK
resource "google_compute_network" "vpc_network" {
  name                    = var.network_name
  auto_create_subnetworks = true
}

### FIREWALL
resource "google_compute_firewall" "all" {
  name = "allow-all"
  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  network       = google_compute_network.vpc_network.id
  source_ranges = ["0.0.0.0/0"]
}

### SUT INSTANCE
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
  metadata_startup_script = file("startup_sut.sh")


  network_interface {
    network = google_compute_network.vpc_network.id
    access_config {
      # Include this section to give the VM an external IP address
    }
  }
}

### BENCHMARK CLIENT INSTANCE
resource "google_compute_instance" "client" {
  name         = "valkey-client-node"
  machine_type = var.client_machine_type

  boot_disk {
    initialize_params {
      image = var.instance_image_client
      size  = var.boot_disk_size_gb
    }
  }
  metadata_startup_script = file("startup_client.sh")


  network_interface {
    network = google_compute_network.vpc_network.id
    access_config {
      # Include this section to give the VM an external IP address
    }
  }
}
