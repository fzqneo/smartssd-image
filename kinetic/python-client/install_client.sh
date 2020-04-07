#!/bin/bash
# Install the appropriate dependicies
echo "# install python-setuptools"
sudo pip install setuptools

echo "# install python-protobuf"
sudo pip install -I protobuf==3.1.0

# Install the client
echo "# install kv_client"
sudo python setup.py develop

echo "# clean up"
sudo python setup.py clean
