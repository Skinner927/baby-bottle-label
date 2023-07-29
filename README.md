# Bottle Label

Run `./start-docker.sh` if you want to launch in a Docker.

To run against the local system:

```shell
sudo adduser --system --no-create-home --group bottle
sudo mkdir /opt/bottle
sudo chown -R bottle:bottle /opt/bottle

sudo -u bottle cp main.py /opt/bottle/main.py
sudo -u bottle python3 -m venv venv
sudo -u bottle ./venv/bin/python -m pip install -U pip wheel setuptools
sudo -u bottle ./venv/bin/python -m pip install --prefer-binary bottle gunicorn
sudo -u bottle ./venv/bin/gunicorn -b 0.0.0.0:7788 -w 4 -n bottle-label main:application

sudo cp systemd/bottle-label.service /etc/systemd/system/bottle-label.service
sudo systemctl enable --now bottle-label
sudo systemctl status bottle-label
```

`gunicorn` is supposed to be put behind a proxy like NGINX, but you shouldn't
be serving hundreds of users.

## Provision Host/Pi

```shell
sudo apt update
sudo apt install -y vim unattended-upgrades dbus-user-session \
  python3 python3-pip python3-venv

sudo vim /etc/vim/vimrc.local
# set mouse=
# set ttymouse=

sudo vim /etc/apt/apt.conf.d/50unattended-upgrades
# Automatic-Reboot "true";
# Automatic-Reboot-Time "02:00";

# Edit static IP in /etc/dhcpcd.conf and reboot

# Install snap for lprint
sudo apt install -y snapd
sudo reboot # YES REBOOT

sudo snap install core
sudo snap install lprint
sudo snap connect lprint:raw-usb
sudo snap stop --disable lprint.lprint-server

# Check lprint is working:
lprint
# If you get an error about a snap cgroup missing run (without sudo)
systemctl --user start dbus.service

# Plug in the DYMO printer
# List devices
sudo /snap/bin/lprint devices
# Mine is usb://DYMO/LabelWriter%20450?serial=01010112345600
# List drivers
sudo /snap/bin/lprint drivers
# Mine is: dymo_lm-450
# Install printer
sudo /snap/bin/lprint add -d dymo450 -v 'usb://DYMO/LabelWriter%20450?serial=01010112345600' -m dymo_lm-450
# Notice mine is named "dymo450", you'll need this for the server config

# TODO: THIS DONT WORK RIGHT
# Create bottle service account
sudo useradd -r bottle
sudo mkdir /srv/bottle
sudo chown -R bottle:bottle /srv/bottle

# Switch to bottle user & init server
sudo su - bottle
cd /srv/bottle
python3 -m venv venv
./venv/bin/python -m pip install -U pip wheel setuptools
```
