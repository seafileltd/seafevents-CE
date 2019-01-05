import os
import ConfigParser
import logging

from .db import init_db_session_class

from .events.db import get_user_activities, save_user_activity, get_file_history

logger = logging.getLogger(__name__)
