import hashlib
import logging
import tempfile
import json
import shutil
import os
import requests
import time
import string
import subprocess

logger = logging.getLogger(__name__)

FRONTEND_DEFUALTBACKEND_LINE = "default_backend %(b)s"
BACKEND_USE_SERVER_LINE = "server %(h)s-%(p)s %(i)s:%(p)s"
PORT = "80"
BALANCER_TYPE = "_PORT_%s_TCP" % PORT
TUTUM_CLUSTER_NAME = "_TUTUM_API_URL"
POLLING_PERIOD = 30

APP_FRONTENDNAME = "http"
APP_BACKENDNAME = "cluster"

TUTUM_AUTH = os.environ.get("TUTUM_AUTH")


def need_to_reload_config(current_filename, new_filename):
    return get_md5_hash_from_file_content(current_filename) != get_md5_hash_from_file_content(new_filename)


def get_md5_hash_from_file_content(filename):
    md5 = hashlib.md5()
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(128*md5.block_size), b''):
            md5.update(chunk)
    return md5.hexdigest()


def add_or_update_app_to_haproxy(dictionary):
    if not dictionary or dictionary == {}:
        return
    outer_ports_and_web_public_dns = dictionary.values()
    logger.info("Adding or updating HAProxy with ports %s", outer_ports_and_web_public_dns)
    cfg = {'frontend': {}, 'backend': {}}

    cfg['frontend'][APP_FRONTENDNAME] = []
    cfg['frontend'][APP_FRONTENDNAME].append(FRONTEND_DEFUALTBACKEND_LINE % {'b': APP_BACKENDNAME})
    cfg['backend'][APP_BACKENDNAME] = ["balance roundrobin"]

    for outer_port_and_dns in outer_ports_and_web_public_dns:

        cfg['backend'][APP_BACKENDNAME].append(BACKEND_USE_SERVER_LINE % {'h': APP_BACKENDNAME,
                                                                          'i': outer_port_and_dns["web_public_dns"],
                                                                          'p': outer_port_and_dns["outer_port"]})

    _update_haproxy_config(new_app_cfg=cfg)


def _update_haproxy_config(new_app_cfg=None):

    try:
        # Temp files
        tempfolder = tempfile.mkdtemp()
        try:

            new_cfg_tmp = '%s/%s' % (tempfolder, 'haproxy.cfg')
            new_cfgjson_tmp = '%s/%s' % (tempfolder, 'new_haproxy.cfg.json')

            # Get empty cfg file
            logger.debug("=> Get empty configuration")
            shutil.copyfile('/etc/haproxy/empty_haproxy.cfg.json', new_cfgjson_tmp)

            # Create new JSON
            logger.debug("=> Reconfigure JSON")
            with open(new_cfgjson_tmp, "r") as emptycfgjson_tmp_file:
                cfg = json.load(emptycfgjson_tmp_file)

            if new_app_cfg:
                for line in new_app_cfg['frontend'][APP_FRONTENDNAME]:
                    if line not in cfg['frontend'][APP_FRONTENDNAME]:
                        cfg['frontend'][APP_FRONTENDNAME].append(line)
                for backend_name, backend_config in new_app_cfg['backend'].iteritems():
                    if backend_name not in cfg['backend']:
                        cfg['backend'][backend_name] = backend_config
                    else:
                        for backend_config_line in backend_config:
                            if backend_config_line not in cfg['backend'][backend_name]:
                                cfg['backend'][backend_name].append(backend_config_line)

            with open(new_cfgjson_tmp, "w") as new_cfgjson_tmp_file:
                json.dump(cfg, new_cfgjson_tmp_file)

            # Check if we need to update cfg file
            if need_to_reload_config(new_cfgjson_tmp, '/etc/haproxy/haproxy.cfg.json'):
                # Put new configuration
                logger.debug("=> Put new configuration")
                with open(new_cfg_tmp, "w") as new_cfg_tmp_file:
                    new_cfg_tmp_file.write(_render_cfg(cfg))
                shutil.move(new_cfgjson_tmp, '/etc/haproxy/haproxy.cfg.json')
                shutil.move(new_cfg_tmp, '/etc/haproxy/haproxy.cfg')

                # Reload haproxy
                logger.debug("=> Reload haproxy")
                cmd = "sudo -S bash -c '/etc/init.d/haproxy reload'"
                process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                process.communicate()
                assert process.returncode == 0, "Error reloading haproxy configuration"

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


def get_haproxy_dict_from_env_vars_dict(env_vars):
    outer_port_list = {}
    cluster_uris = {}

    for env_var, value in env_vars.iteritems():
        position = string.find(env_var, BALANCER_TYPE)
        if position != -1:
            container_name = env_var[:position]
            container_values = outer_port_list.get(container_name, {'web_public_dns': None, 'outer_port': None})
            if env_var.endswith(BALANCER_TYPE + "_ADDR"):
                container_values['web_public_dns'] = value
            elif env_var.endswith(BALANCER_TYPE + "_PORT"):
                container_values['outer_port'] = value
            outer_port_list[container_name] = container_values

        position = string.find(env_var, TUTUM_CLUSTER_NAME)
        if position != -1 and env_var.endswith(TUTUM_CLUSTER_NAME):
            cluster_name = env_var[:position]
            cluster_uris[cluster_name] = value

    return outer_port_list, cluster_uris


if __name__ == "__main__":
    logging.basicConfig()

    logger.debug("Balancer: HAProxy service is Running")
    session = requests.Session()
    headers = {"Authorization": TUTUM_AUTH}

    while True:
        try:
            # Get balancer dictionary and clusters from env vars
            balancer_dictionary_from_env_vars, clusters = get_haproxy_dict_from_env_vars_dict(os.environ)

            if clusters != {}:
                for cluster_name, uri in clusters.iteritems():

                    # Get container cluster info
                    r = session.get(uri, headers=headers)
                    if r.status_code != 200:
                        raise Exception("Request url %s gives us a %d error code", r.status_code)
                    else:
                        r.raise_for_status()

                    container_cluster_info = r.json()
                    logger.debug("Balancer: Container Cluster info. %s", container_cluster_info)

                    cluster_balancer_dict, _ = get_haproxy_dict_from_env_vars_dict(container_cluster_info["link_variables"])
                    balancer_dictionary_from_env_vars.update(cluster_balancer_dict)

                    old_cluster_member_names = [c_name for c_name in balancer_dictionary_from_env_vars.keys() if c_name.startswith(cluster_name)]

                    containers_to_delete = [c_name for c_name in old_cluster_member_names if c_name not in cluster_balancer_dict.keys()]

                    for container in containers_to_delete:
                        balancer_dictionary_from_env_vars.pop(container)

            logger.debug("Balancer: Add or Update HAProxy with env vars: %s", balancer_dictionary_from_env_vars)
            add_or_update_app_to_haproxy(balancer_dictionary_from_env_vars)

        except Exception:
            logger.exception("Error")
            pass
        time.sleep(POLLING_PERIOD)