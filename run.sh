#!/bin/bash

if [ "${SSL_CERT}" = "**None**" ]; then
    unset SSL_CERT 
fi

if [ -n "$SSL_CERT" ]; then
    echo "Found ssl certificate, start https proxy"
    mkdir -p /certs
    echo -e "${SSL_CERT}" > /certs/server.pem
    cp /conf/haproxy.cfg.json.ssl /etc/haproxy/haproxy.cfg.json
    cp /conf/haproxy.cfg.json.ssl /etc/haproxy/empty_haproxy.cfg.json
    cp /conf/haproxy.cfg.ssl /etc/haproxy/haproxy.cfg
else
    echo "No ssl certificate is found, start http proxy"
    cp /conf/haproxy.cfg.json /etc/haproxy/haproxy.cfg.json
    cp /conf/haproxy.cfg.json /etc/haproxy/empty_haproxy.cfg.json
    cp /conf/haproxy.cfg /etc/haproxy/haproxy.cfg
fi

exec python /main.py 
