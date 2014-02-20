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

logger = logging.getLogger(__name__)

FRONTEND_HTTP_ACL_LINE = "acl is_%(b)s hdr(host) -i %(h)s"
FRONTEND_HTTP_USEBACKEND_LINE = "use_backend %(b)s if is_%(b)s"
BACKEND_USE_SERVER_LINE = "server %(h)s-%(p)s %(i)s:%(p)s"

CONTAINER_CLUSTER_UUID = os.environ.get('CONTAINER_CLUSTER_UUID')
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


def add_or_update_app_to_haproxy(server_supervisor, url, docker_ports, node_public_ip="localhost"):
    logger.info("Adding URL %s with ports %s", url, docker_ports)
    if not isinstance(docker_ports, list):
        docker_ports = [docker_ports]
    if not docker_ports or not url:
        return
    app_backendname = hashlib.sha224(url).hexdigest()[:16]
    cfg = {'frontend': {}, 'backend': {}}
    cfg['frontend']['http'] = []
    cfg['frontend']['http'].append(FRONTEND_HTTP_ACL_LINE % {'b': app_backendname, 'h': url})
    cfg['frontend']['http'].append(FRONTEND_HTTP_USEBACKEND_LINE % {'b': app_backendname})
    cfg['backend'][app_backendname] = ["balance roundrobin"]
    for port in docker_ports:
        cfg['backend'][app_backendname].append(BACKEND_USE_SERVER_LINE % {'h': app_backendname, 'i': node_public_ip, 'p': port})
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
                for line in new_app_cfg['frontend']['http']:
                    if line not in cfg['frontend']['http']:
                        cfg['frontend']['http'].append(line)
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

    try:
        server.supervisor.getProcessInfo(HAPROXY_PROCESS_NAME)
    except Exception:
        print "HAProxy service is not configured in supervisor"
        sys.exit(1)

    while True:
        try:
            # Get all running containers
            # Get each container and its outer port
            # Call to add_or_update_app_to_haproxy
            pass
        except Exception as e:
            print "ERROR: %s" % e
            pass