import hashlib
import logging
import xmlrpclib
import supervisor.xmlrpc
import sys
import tempfile
import json
import shutil
import os
import signal
import requests
import time

logger = logging.getLogger(__name__)

FRONTEND_USEBACKEND_LINE = "use_backend %(b)s if is_%(b)s"
FRONTEND_BIND_LINE = "bind :%d"
BACKEND_USE_SERVER_LINE = "server %(h)s-%(p)s %(i)s:%(p)s"

RESOURCE_URI = os.environ.get('RESOURCE_URI')
TUTUM_AUTH = os.environ.get("TUTUM_AUTH")
TUTUM_API_HOST = os.environ.get("TUTUM_API_HOST", "https://app.tutum.co")
TUTUM_POLLING_PERIOD = os.environ.get("TUTUM_POLLING_PERIOD", 30)

HAPROXY_PROCESS_NAME = "haproxy"


def need_to_reload_config(current_filename, new_filename):

    with open(current_filename) as original_file:
        # read contents of the file
        data = original_file.read()
        # pipe contents of the file through
        original_md5 = hashlib.md5(data).hexdigest()

    with open(new_filename) as new_file:
        # read contents of the file
        data = new_file.read()
        # pipe contents of the file through
        new_md5 = hashlib.md5(data).hexdigest()

    return original_md5 != new_md5


def add_or_update_app_to_haproxy(server_supervisor, ports_to_balance):
    logger.info("Adding or updating HAProxy with ports %s", ports_to_balance)
    if not ports_to_balance:
        return
    cfg = {'frontend': {}, 'backend': {}}
    for inner_port, outer_port_list in ports_to_balance.iteritems():
        app_frontendname = hashlib.sha224("frontend_"+str(inner_port)).hexdigest()[:16]
        app_backendname = "cluster_" + app_frontendname

        cfg['frontend'][app_frontendname] = []
        cfg['frontend'][app_frontendname].append(FRONTEND_BIND_LINE % inner_port)
        cfg['frontend'][app_frontendname].append(FRONTEND_USEBACKEND_LINE % {'b': app_backendname})
        cfg['backend'][app_backendname] = ["balance roundrobin"]
        for port in outer_port_list:
            cfg['backend'][app_backendname].append(BACKEND_USE_SERVER_LINE % {'h': app_backendname,
                                                                              'i': port["public_dns"],
                                                                              'p': port["outer_port"]})
    _update_haproxy_config(server_supervisor, new_app_cfg=cfg)


def _update_haproxy_config(server_supervisor, new_app_cfg=None):
    if not new_app_cfg: new_app_cfg = []

    try:
        # Temp files
        tempfolder = tempfile.mkdtemp()
        try:

            cfgjson_tmp = '%s/%s' % (tempfolder, 'haproxy.cfg.json')
            cfg_tmp = '%s/%s' % (tempfolder, 'haproxy.cfg')
            emptycfgjson_tmp = '%s/%s' % (tempfolder, 'empty_haproxy.cfg.json')

            # Get cfg file and its md5
            logger.debug("=> Get current configuration")
            shutil.copyfile('/etc/haproxy/haproxy.cfg.json', emptycfgjson_tmp)

            # Reconfigure JSON
            logger.debug("=> Reconfigure JSON")
            with open(emptycfgjson_tmp, "r") as cfgjson_tmp_file:
                cfg = json.load(cfgjson_tmp_file)

            if new_app_cfg:
                for app_frontendname, frontend_config in new_app_cfg['frontend'].iteritems():
                    for line in frontend_config:
                        if line not in cfg['frontend'][app_frontendname]:
                            cfg['frontend'][app_frontendname].append(line)
                    for backend_name, backend_config in new_app_cfg['backend'].iteritems():
                        if backend_name not in cfg['backend']:
                            cfg['backend'][backend_name] = backend_config
                        else:
                            for backend_config_line in backend_config:
                                if backend_config_line not in cfg['backend'][backend_name]:
                                    cfg['backend'][backend_name].append(backend_config_line)

            with open(cfgjson_tmp, "w") as cfgjson_tmp_file:
                json.dump(cfg, cfgjson_tmp_file)

            # Reconfigure CFG file
            logger.debug("=> Reconfigure CFG")
            with open(cfg_tmp, "w") as cfg_tmp_file:
                cfg_tmp_file.write(_render_cfg(cfg))

            haproxy_process_info = server_supervisor.getProcessInfo(HAPROXY_PROCESS_NAME)
            # HAProxy process is not running
            if haproxy_process_info['state'] != 1:
                logger.debug("=> Initial configuration")
                shutil.move(cfgjson_tmp, '/etc/haproxy/haproxy.cfg.json')
                shutil.move(cfg_tmp, '/etc/haproxy/haproxy.cfg')

                # Start HAProxy
                logger.debug("=> Start haproxy")
                server_supervisor.startProcess(HAPROXY_PROCESS_NAME, wait=True)

            # Check if we need to update cfg file
            elif haproxy_process_info['state'] == 1 and need_to_reload_config(cfg_tmp, '/etc/haproxy/haproxy.cfg'):
                # Put new configuration
                logger.debug("=> Put new configuration")
                shutil.move(cfgjson_tmp, '/etc/haproxy/haproxy.cfg.json')
                shutil.move(cfg_tmp, '/etc/haproxy/haproxy.cfg')

                # Reload haproxy
                logger.debug("=> Reload haproxy")
                os.kill(haproxy_process_info['pid'], signal.SIGHUP)

        except Exception:
            raise
        finally:
            # Remove temp dir
            shutil.rmtree(tempfolder)

    except Exception, e:
        logger.error('*** Caught exception: %s: %s', e.__class__, e)
        raise


def _render_cfg(cfg):
    out = ""
    for section in "global", "defaults":
        out += '%s\n' % section
        for value in cfg[section]:
            out += '\t%s\n' % value

    for section in "frontend", "backend":
        for header, values in cfg[section].iteritems():
            out += '%s %s\n' % (section, header)
            for value in values:
                out += '\t%s\n' % value

    return out


if __name__ == "__main__":
    logging.basicConfig()
    server = xmlrpclib.ServerProxy('http://127.0.0.1',
                                   transport=supervisor.xmlrpc.SupervisorTransport(None,
                                                                                   None,
                                                                                   serverurl='unix:///tmp/'
                                                                                             'supervisor.sock'))

    if server.supervisor.getState()['statecode'] != 1:
        print "Supervisor is not running"
        sys.exit(1)

    logger.debug("Balancer: supervisor is Running")
    try:
        server.supervisor.getProcessInfo(HAPROXY_PROCESS_NAME)
    except Exception:
        print "HAProxy service is not configured in supervisor"
        sys.exit(1)

    logger.debug("Balancer: HAProxy service is Running")
    session = requests.Session()
    request_url = "%s%s" % (TUTUM_API_HOST, RESOURCE_URI)
    headers = {"Authorization": TUTUM_AUTH}

    while True:
        try:
            # Get HAProxy Process Info
            haproxy_process_info = server.supervisor.getProcessInfo(HAPROXY_PROCESS_NAME)
            logger.debug("Balancer: HAProxy service info. %s", haproxy_process_info)

            # Get all containers from the container cluster
            r = session.get(request_url, headers=headers)
            if r.status_code != 200:
                raise Exception("Request url %s gives us a %d error code", r.status_code)
            else:
                r.raise_for_status()

            container_cluster_info = r.json()
            logger.debug("Balancer: Container Cluster info. %s", container_cluster_info)

            if container_cluster_info["state"] not in ["Running", "Partly Running"] \
                    and haproxy_process_info["state"] == 1:
                logger.debug("=> Stop haproxy")
                server.supervisor.stopProcess(HAPROXY_PROCESS_NAME, wait=True)
            elif container_cluster_info["state"] in ["Running", "Partly Running"]:
                ports_to_balance = {}

                # Get all running containers and outer ports
                logger.debug("Balancer: Getting containers from container cluster %s",
                             container_cluster_info["uuid"])
                for container in container_cluster_info["containers"]:
                    logger.debug("Balancer: Getting info from container %s", container)
                    container_url = "%s%s" % (TUTUM_API_HOST, container)
                    r = session.get(container_url, headers=headers)

                    if r.status_code != 200:
                        raise Exception("Request url %s gives us a %d error code", r.status_code)
                    else:
                        r.raise_for_status()

                    container_info = r.json()
                    logger.debug("Balancer: Info from container %s", container_info)
                    if container_info["state"] == "Running":
                        for port in container_info["container_ports"]:
                            if port["protocol"] == "tcp":
                                outer_port_list = ports_to_balance.get(port["inner_port"], [])
                                outer_port_list.append({"outer_port": port["outer_port"],
                                                        "public_dns": container_info["public_dns"]})
                                ports_to_balance[port["inner_port"]] = outer_port_list

                # Call to add_or_update_app_to_haproxy
                logger.debug("Balancer: Add or Update HAProxy: %s", ports_to_balance)
                add_or_update_app_to_haproxy(server.supervisor, ports_to_balance)

        except Exception as e:
            print "ERROR: %s" % e
            pass
        time.sleep(TUTUM_POLLING_PERIOD)