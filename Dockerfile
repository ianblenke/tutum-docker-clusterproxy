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
ADD conf/ /conf/ 

# PORT to load balance and to expose (also update the EXPOSE directive below)
ENV PORT 80
# MODE of operation (http, tcp)
ENV MODE http
# algorithm for load balancing (roundrobin, source, leastconn, ...)
ENV BALANCE roundrobin

ENV SSL_CERT **None**

EXPOSE 443 80
CMD ["/run.sh"]
