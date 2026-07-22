#!/bin/bash
# set_proxy.sh

# Set environment variables for proxy
export http_proxy="http://10.100.1.2:8123"
export https_proxy="http://10.100.1.2:8123"
export no_proxy="localhost,127.0.0.1,10.100.0.21,10.100.200.71,smartproxydmscdaq01.esss.dk,puppetdb6prod01.esss.dk,scicatingestor07.daq.esss.dk,scicatingestor07"

# Configure apt to use the proxy
echo 'Acquire::http::Proxy "'$http_proxy'";' > /etc/apt/apt.conf.d/01proxy
echo 'Acquire::https::Proxy "'$https_proxy'";' >> /etc/apt/apt.conf.d/01proxy
echo 'Acquire::http::Proxy::no_proxy "'$no_proxy'";' >> /etc/apt/apt.conf.d/01proxy

