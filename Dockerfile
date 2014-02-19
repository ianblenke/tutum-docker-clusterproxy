FROM ubuntu:latest
MAINTAINER Bernardo Pericacho <bernardo@tutum.co>

# Install required packages
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y haproxy supervisor

# Add configuration and scripts
ADD https://raw.github.com/tutumcloud/tutum-docker-clusterproxy/master/haproxy.cfg /etc/haproxy/haproxy.cfg
ADD https://raw.github.com/tutumcloud/tutum-docker-clusterproxy/master/haproxy.cfg.json /etc/haproxy/haproxy.cfg.json
ADD https://raw.github.com/tutumcloud/tutum-docker-clusterproxy/master/supervisord-haproxy.conf /etc/supervisor/conf.d/supervisord-haproxy.conf
ADD https://raw.github.com/tutumcloud/tutum-docker-clusterproxy/master/run.sh /run.sh
RUN chmod 755 /*.sh

CMD ["/run.sh"]
