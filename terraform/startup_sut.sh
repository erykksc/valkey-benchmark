export DEBIAN_FRONTEND=noninteractive
sudo apt update
sudo apt upgrade -y
sudo apt install -y -q apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository --yes "deb [arch=amd64] https://download.docker.com/linux/ubuntu focal stable"
sudo apt update
sudo apt upgrade -y
sudo apt install -y -q docker-ce

#Start docker
sudo service docker-ce start
echo "Start VictoriaMetrics ..."
# flags: https://github.com/VictoriaMetrics/VictoriaMetrics#list-of-command-line-flags
sudo docker run -d --rm -v $(pwd)/victoria-metrics-data:/victoria-metrics-data -p 8428:8428 victoriametrics/victoria-metrics:latest -retentionPeriod=4
echo "Container started on port 8428"

touch /done
