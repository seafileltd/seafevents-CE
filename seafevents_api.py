from seafevents.app.config import appconfig, load_config
from .events.db import get_new_file_path, get_user_activities_by_timestamp

def init(config_file):
    if not appconfig.get('session_cls'):
        load_config(config_file)

def is_pro():
    return False

def get_file_history_suffix():
    if appconfig.fh.enabled is False:
        return None

    return appconfig.fh.suffix_list
