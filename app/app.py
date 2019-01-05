import os
import libevent
import logging

from sqlalchemy.ext.declarative import declarative_base

import ccnet
from ccnet.async import AsyncClient

from seafevents.app.config import appconfig, load_config
from seafevents.app.signal_handler import SignalHandler
from seafevents.app.mq_listener import EventsMQListener
from seafevents.utils import do_exit, ClientConnector, get_config

Base = declarative_base()

class App(object):
    def __init__(self, ccnet_dir, args, events_listener_enabled=True):
        self._ccnet_dir = ccnet_dir
        self._central_config_dir = os.environ.get('SEAFILE_CENTRAL_CONF_DIR')
        self._args = args
        self._events_listener_enabled = events_listener_enabled
        try:
            load_config(args.config_file)
        except Exception as e:
            logging.error('Error loading seafevents config. Detial: %s' % e)
            raise RuntimeError("Error loading seafevents config. Detial: %s" % e)

        self._events_listener = None
        if self._events_listener_enabled:
            self._events_listener = EventsMQListener(self._args.config_file)

        self._ccnet_session = None
        self._sync_client = None

        self._evbase = libevent.Base() #pylint: disable=E1101
        self._sighandler = SignalHandler(self._evbase)

    def start_ccnet_session(self):
        '''Connect to ccnet-server, retry util connection is made'''
        self._ccnet_session = AsyncClient(self._ccnet_dir,
                                          self._evbase,
                                          central_config_dir=self._central_config_dir)
        connector = ClientConnector(self._ccnet_session)
        connector.connect_daemon_with_retry()

        self._sync_client = ccnet.SyncClient(self._ccnet_dir,
                                             central_config_dir=self._central_config_dir)
        self._sync_client.connect_daemon()

    def connect_ccnet(self):
        self.start_ccnet_session()

        if self._events_listener:
            try:
                self._sync_client.register_service_sync('seafevents-events-dummy-service', 'rpc-inner')
            except:
                logging.exception('Another instance is already running')
                do_exit(1)
            self._events_listener.start(self._ccnet_session)

    def _serve(self):
        try:
            self._ccnet_session.main_loop()
        except ccnet.NetworkError:
            logging.warning('connection to ccnet-server is lost')
            if self._args.reconnect:
                self.connect_ccnet()
            else:
                do_exit(0)
        except Exception:
            logging.exception('Error in main_loop:')
            do_exit(0)

    def serve_forever(self):
        self.connect_ccnet()

        while True:
            self._serve()

