FROM ubuntu:trusty
MAINTAINER Bernardo Pericacho <bernardo@tutum.co> && Feng Honglin <hfeng@tutum.co>

RUN apt-get update &&  DEBIAN_FRONTEND=noninteractive apt-get install -y software-properties-common && add-apt-repository ppa:vbernat/haproxy-1.5

# Install required packages
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y haproxy python-pip

# Add configuration and scripts
ADD requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

ADD main.py /main.py
ADD run.sh /run.sh
RUN chmod 755 /*.sh
ADD conf/haproxy.cfg.json /etc/haproxy/haproxy.cfg.json
ADD conf/haproxy.cfg.json /etc/haproxy/empty_haproxy.cfg.json

# PORT to load balance and to expose (also update the EXPOSE directive below)
ENV PORT 80
# MODE of operation (http, tcp)
ENV MODE http
# algorithm for load balancing (roundrobin, source, leastconn, ...)
ENV BALANCE roundrobin
# maximum number of connections
ENV MAXCONN 4096
# list of options separated by commas
ENV OPTIONS redispatch
# list of timeout entries separated by commas
ENV TIMEOUTS connect 5000,client 50000,server 50000
# SSL certificate to use (optional)
ENV SSL_CERT **None**

EXPOSE 80
CMD ["/run.sh"]
