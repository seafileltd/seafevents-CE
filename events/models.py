# coding: utf-8

import json
import uuid
import hashlib

from sqlalchemy import Column, Integer, String, DateTime, Text, Index, BigInteger
from sqlalchemy import ForeignKey, Sequence

from seafevents.db import Base

class Activity(Base):
    """
    """
    __tablename__ = 'Activity'

    id = Column(Integer, Sequence('activity_seq'), primary_key=True)
    op_type = Column(String(length=128), nullable=False)
    op_user = Column(String(length=255), nullable=False)
    obj_type = Column(String(length=128), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)

    repo_id = Column(String(length=36), nullable=False)
    commit_id = Column(String(length=40))
    path = Column(Text, nullable=False)
    detail = Column(Text, nullable=False)

    def __init__(self, record):
        self.op_type = record['op_type']
        self.obj_type = record['obj_type']
        self.repo_id = record['repo_id']
        self.timestamp = record['timestamp']
        self.op_user = record['op_user']
        self.path = record['path']
        self.commit_id = record.get('commit_id', None)


        detail = {}
        detail_keys = ['size', 'old_path', 'days', 'repo_name', 'obj_id', 'old_repo_name']
        for k in detail_keys:
            if record.has_key(k) and record.get(k, None) is not None:
                detail[k] = record.get(k, None)

        self.detail = json.dumps(detail)

    def __str__(self):
        return 'Activity<id: %s, type: %s, repo_id: %s>' % \
            (self.id, self.op_type, self.repo_id)


class UserActivity(Base):
    """
    """
    __tablename__ = 'UserActivity'

    id = Column(Integer, Sequence('useractivity_seq'), primary_key=True)
    username = Column(String(length=255), nullable=False)
    activity_id = Column(Integer, ForeignKey('Activity.id', ondelete='CASCADE'))
    timestamp = Column(DateTime, nullable=False, index=True)

    __table_args__ = (Index('idx_username_timestamp',
                            'username', 'timestamp'),)

    def __init__(self, username, activity_id, timestamp):
        self.username = username
        self.activity_id = activity_id
        self.timestamp = timestamp

    def __str__(self):
        return 'UserActivity<username: %s, activity id: %s>' % \
                (self.username, self.activity_id)

class FileHistory(Base):
    __tablename__ = 'FileHistory'

    id = Column(Integer, Sequence('user_event_eid_seq'), primary_key=True)
    op_type = Column(String(length=128), nullable=False)
    op_user = Column(String(length=255), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)

    repo_id = Column(String(length=36), nullable=False)
    commit_id = Column(String(length=40))
    file_id =  Column(String(length=40), nullable=False)
    file_uuid = Column(String(length=40), index=True)
    path = Column(Text, nullable=False)
    repo_id_path_md5 = Column(String(length=32), index=True)
    size = Column(BigInteger, nullable=False)
    old_path = Column(Text, nullable=False)

    def __init__(self, record):
        self.op_type = record['op_type']
        self.op_user = record['op_user']
        self.timestamp = record['timestamp']
        self.repo_id = record['repo_id']
        self.commit_id = record.get('commit_id', '')
        self.file_id = record.get('obj_id')
        self.file_uuid = record.get('file_uuid')
        self.path = record['path']
        self.repo_id_path_md5 = hashlib.md5((self.repo_id + self.path).encode('utf8')).hexdigest()
        self.size = record.get('size')
        self.old_path = record.get('old_path', '')
