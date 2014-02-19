FROM ubuntu:latest
MAINTAINER Bernardo Pericacho <bernardo@tutum.co>

# Install and HAProxy configuration
RUN apt-get update && apt-get install -y haproxy
ADD https://github.com/tutumcloud/tutum-docker-clusterproxy/master/HAProxy.cfg /etc/haproxy/haproxy.cfg
RUN sed -i s/ENABLED=0/ENABLED=1/g /etc/default/haproxy

# Run HAProxy
ADD https://raw.github.com/tutumcloud/tutum-docker-clusterproxy/master/run.sh /run.sh
RUN chmod 755 /*.sh

CMD ["/run.sh"]