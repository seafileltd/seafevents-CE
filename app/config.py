import os
import logging
from seafevents.db import init_db_session_class
from seafevents.utils import get_config

class AppConfig(object):
    def __init__(self):
        pass

    def set(self, key, value):
        self.key = value

    def get(self, key):
        if hasattr(self, key):
            return self.__dict__[key]
        else:
            return ''

appconfig = AppConfig()

def exception_catch(conf_module):
    """Catch exceptions for functions and log them
    """
    def func_wrapper(func):
        def wrapper(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except Exception as e:
                logging.info('%s module configuration loading failed: %s' % (conf_module, e))
        return wrapper
    return func_wrapper

def load_config(config_file):
    # seafevent config file
    appconfig.session_cls = init_db_session_class(config_file)
    config = get_config(config_file)

    load_env_config()
    load_file_history_config(config)

@exception_catch('env')
def load_env_config():
    # get central config dir
    appconfig.central_confdir = ""
    if 'SEAFILE_CENTRAL_CONF_DIR' in os.environ:
        appconfig.central_confdir = os.environ['SEAFILE_CENTRAL_CONF_DIR']

    # get seafile config path
    appconfig.seaf_conf_path = ""
    if appconfig.central_confdir:
        appconfig.seaf_conf_path = os.path.join(appconfig.central_confdir, 'seafile.conf')
    elif 'SEAFILE_CONF_DIR' in os.environ:
        appconfig.seaf_conf_path = os.path.join(os.environ['SEAFILE_CONF_DIR'], 'seafile.conf')

    # get ccnet config path
    appconfig.ccnet_conf_path = ""
    if appconfig.central_confdir:
        appconfig.ccnet_conf_path = os.path.join(appconfig.central_confdir, 'ccnet.conf')
    elif 'CCNET_CONF_DIR' in os.environ:
        appconfig.ccnet_conf_path = os.path.join(os.environ['CCNET_CONF_DIR'], 'ccnet.conf')

@exception_catch('file history')
def load_file_history_config(config):
    appconfig.fh = AppConfig()
    appconfig.fh.enabled =  False
    if config.has_option('FILE HISTORY', 'enabled'):
        appconfig.fh.enabled = config.getboolean('FILE HISTORY', 'enabled')
    if appconfig.fh.enabled:
        appconfig.fh.suffix = config.get('FILE HISTORY', 'suffix')
        suffix = appconfig.fh.suffix.strip(',')
        appconfig.fh.suffix_list = suffix.split(',') if suffix else []
        logging.info('The file with the following suffix will be recorded into the file history: %s' % suffix)
    else:
        logging.info('Disenabled File History Features.')
