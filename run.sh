#!/bin/bash

if [ "${SSL_CERT}" = "**None**" ]; then
    unset SSL_CERT 
fi

if [ -n "$SSL_CERT" ]; then
    echo "Found ssl certificate"
    mkdir -p /certs
    echo -e "${SSL_CERT}" > /certs/server.pem
    cp /conf/haproxy-ssl.cfg.json /etc/haproxy/haproxy.cfg.json
    cp /conf/haproxy-ssl.cfg.json /etc/haproxy/empty_haproxy.cfg.json
else
    echo "No ssl certificate found"
    cp /conf/haproxy.cfg.json /etc/haproxy/haproxy.cfg.json
    cp /conf/haproxy.cfg.json /etc/haproxy/empty_haproxy.cfg.json
fi

exec python /main.py 
