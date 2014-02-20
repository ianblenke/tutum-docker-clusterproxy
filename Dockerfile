FROM ubuntu:latest
MAINTAINER Bernardo Pericacho <bernardo@tutum.co>

# Install required packages
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y haproxy supervisor python-pip

# Add configuration and scripts
ADD https://raw.github.com/tutumcloud/tutum-docker-clusterproxy/master/haproxy.cfg /etc/haproxy/haproxy.cfg
ADD https://raw.github.com/tutumcloud/tutum-docker-clusterproxy/master/haproxy.cfg /etc/haproxy/empty_haproxy.cfg
ADD https://raw.github.com/tutumcloud/tutum-docker-clusterproxy/master/haproxy.cfg.json /etc/haproxy/haproxy.cfg.json
ADD https://raw.github.com/tutumcloud/tutum-docker-clusterproxy/master/supervisord-haproxy.conf /etc/supervisor/conf.d/supervisord-haproxy.conf
ADD https://raw.github.com/tutumcloud/tutum-docker-clusterproxy/master/supervisord-httpserver.conf /etc/supervisor/conf.d/supervisord-httpserver.conf
ADD https://raw.github.com/tutumcloud/tutum-docker-clusterproxy/master/requirements.txt /requirements.txt
ADD https://raw.github.com/tutumcloud/tutum-docker-clusterproxy/master/supervisord-balancer.conf /etc/supervisor/conf.d/supervisord-balancer.conf
ADD https://raw.github.com/tutumcloud/tutum-docker-clusterproxy/master/main.py /main.py
ADD https://raw.github.com/tutumcloud/tutum-docker-clusterproxy/master/run.sh /run.sh
RUN chmod 755 /*.sh
RUN pip install -r /requirements.txt

CMD ["/run.sh"]
