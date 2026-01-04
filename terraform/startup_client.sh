#Autostart services https://askubuntu.com/questions/1367139/apt-get-upgrade-auto-restart-services
export DEBIAN_FRONTEND=noninteractive

sudo apt update
sudo apt upgrade -y
sudo apt install -y -q git
sudo apt install -y -q golang-go
sudo apt install -y -q make

touch /done
