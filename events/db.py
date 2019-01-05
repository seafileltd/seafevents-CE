import json
import uuid
import logging
import datetime
from datetime import timedelta
import hashlib

from sqlalchemy import desc
from sqlalchemy.sql import exists

from .models import Activity, UserActivity, FileHistory

from seafevents.app.config import appconfig

logger = logging.getLogger('seafevents')

class UserActivityDetail(object):
    """Regular objects which can be used by seahub without worrying about ORM"""
    def __init__(self, event, username=None):
        self.username = username

        self.id = event.id
        self.op_type = event.op_type
        self.op_user = event.op_user
        self.obj_type = event.obj_type
        self.repo_id = event.repo_id
        self.commit_id = event.commit_id
        self.timestamp = event.timestamp
        self.path = event.path

        dt = json.loads(event.detail)
        for key in dt:
            self.__dict__[key] = dt[key]

    def __getitem__(self, key):
        return self.__dict__[key]

def _get_user_activities(session, username, start, limit):
    if start < 0:
        raise RuntimeError('start must be non-negative')

    if limit <= 0:
        raise RuntimeError('limit must be positive')

    q = session.query(Activity).filter(UserActivity.username == username)
    q = q.filter(UserActivity.activity_id == Activity.id)

    events = q.order_by(desc(UserActivity.timestamp)).slice(start, start + limit).all()

    return [ UserActivityDetail(ev, username=username) for ev in events ]

def get_user_activities(session, username, start, limit):
    return _get_user_activities(session, username, start, limit)

def _get_user_activities_by_timestamp(username, start, end):
    events = []
    try:
        session = appconfig.session_cls()
        q = session.query(Activity).filter(UserActivity.username == username,
                                           UserActivity.timestamp.between(start, end))
        q = q.filter(UserActivity.activity_id == Activity.id)

        events = q.order_by(UserActivity.timestamp).all()
    except Exception as e:
        logging.warning('Failed to get activities of %s: %s.', username, e)
    finally:
        session.close()

    return [ UserActivityDetail(ev, username=username) for ev in events ]

def get_user_activities_by_timestamp(username, start, end):
    return _get_user_activities_by_timestamp(username, start, end)

def get_file_history(session, repo_id, path, start, limit):
    repo_id_path_md5 = hashlib.md5((repo_id + path).encode('utf8')).hexdigest()
    current_item = session.query(FileHistory).filter(FileHistory.repo_id_path_md5 == repo_id_path_md5)\
            .order_by(desc(FileHistory.timestamp)).first()

    events = []
    total_count = 0
    if current_item:
        total_count = session.query(FileHistory).filter(FileHistory.file_uuid == current_item.file_uuid).count()
        q = session.query(FileHistory).filter(FileHistory.file_uuid == current_item.file_uuid)\
                .order_by(desc(FileHistory.timestamp)).slice(start, start + limit + 1)

        # select Event.etype, Event.timestamp, UserEvent.username from UserEvent, Event where UserEvent.username=username and UserEvent.org_id <= 0 and UserEvent.eid = Event.uuid order by UserEvent.id desc limit 0, 15;
        events = q.all()
        if events and len(events) == limit + 1:
            next_start = start + limit
            events = events[:-1]

    return events, total_count

def not_include_all_keys(record, keys):
    return any(record.get(k, None) is None for k in keys)

def save_user_activity(session, record):
    activity = Activity(record)
    session.add(activity)
    session.commit()
    for username in record['related_users']:
        user_activity = UserActivity(username, activity.id, record['timestamp'])
        session.add(user_activity)
    session.commit()

def update_user_activity_timestamp(session, activity_id, record):
    q = session.query(Activity).filter(Activity.id==activity_id)
    q = q.update({"timestamp": record["timestamp"]})
    q = session.query(UserActivity).filter(UserActivity.activity_id==activity_id)
    q = q.update({"timestamp": record["timestamp"]})
    session.commit()

def update_file_history_record(session, history_id, record):
    q = session.query(FileHistory).filter(FileHistory.id==history_id)
    q = q.update({"timestamp": record["timestamp"],
                  "file_id": record["obj_id"],
                  "commit_id": record["commit_id"],
                  "size": record["size"]})
    session.commit()

def query_prev_record(session, record):
    if record['op_type'] == 'create':
        return None

    if record['op_type'] in ['rename', 'move']:
        repo_id_path_md5 = hashlib.md5((record['repo_id'] + record['old_path']).encode('utf8')).hexdigest()
    else:
        repo_id_path_md5 = hashlib.md5((record['repo_id'] + record['path']).encode('utf8')).hexdigest()

    q = session.query(FileHistory)
    prev_item = q.filter(FileHistory.repo_id_path_md5 == repo_id_path_md5).order_by(desc(FileHistory.timestamp)).first()

    # The restore operation may not be the last record to be restored, so you need to switch to the last record
    if record['op_type'] == 'recover':
        q = session.query(FileHistory)
        prev_item = q.filter(FileHistory.file_uuid == prev_item.file_uuid).order_by(desc(FileHistory.timestamp)).first()

    return prev_item

def save_filehistory(session, record):
    # use same file_uuid if prev item already exists, otherwise new one
    prev_item = query_prev_record(session, record)
    if prev_item:
        # If a file was edited many times in 10 minutes, just update timestamp.
        dt = datetime.datetime.utcnow()
        delta = timedelta(minutes=10)
        if record['op_type'] == 'edit' and prev_item.op_type == 'edit' \
                                       and prev_item.op_user == record['op_user'] \
                                       and prev_item.timestamp > dt - delta:
            update_file_history_record(session, prev_item.id, record)
            return

        if record['path'] != prev_item.path and record['op_type'] == 'recover':
            pass
        else:
            record['file_uuid'] = prev_item.file_uuid

    if not record.has_key('file_uuid'):
        file_uuid = uuid.uuid4()
        # avoid hash conflict
        while session.query(exists().where(FileHistory.file_uuid == file_uuid)).scalar():
            file_uuid = uuid.uuid4()
        record['file_uuid'] = file_uuid

    filehistory = FileHistory(record)
    session.add(filehistory)
    session.commit()

# If a file was moved or renamed, find the new file by old path.
def get_new_file_path(repo_id, old_path):
    ret = None
    repo_id_path_md5 = hashlib.md5((repo_id + old_path).encode('utf8')).hexdigest()
    try:
        session = appconfig.session_cls()
        q = session.query(FileHistory.file_uuid).filter(FileHistory.repo_id_path_md5==repo_id_path_md5)
        q = q.order_by(desc(FileHistory.timestamp))
        file_uuid = q.first()[0]
        if not file_uuid:
            session.close()
            return None

        q = session.query(FileHistory.path).filter(FileHistory.file_uuid==file_uuid)
        q = q.order_by(desc(FileHistory.timestamp))
        ret = q.first()[0]
    except Exception as e:
        logging.warning('Failed to get new file path for %.8s:%s: %s.', repo_id, old_path, e)
    finally:
        session.close()

    return ret
