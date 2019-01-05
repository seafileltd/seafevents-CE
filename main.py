#!/usr/bin/env python
#coding: utf-8

import argparse
import ConfigParser
import os

from seafevents.utils import write_pidfile, get_config
from seafevents.app.log import LogConfigurator
from seafevents.app.app import App
from seafevents.app.mq_listener import init_message_handlers


class AppArgParser(object):
    def __init__(self):
        self._parser = argparse.ArgumentParser(
            description='seafevents main program')

        self._add_args()

    def parse_args(self):
        return self._parser.parse_args()

    def _add_args(self):
        self._parser.add_argument(
            '--logfile',
            help='log file')

        self._parser.add_argument(
            '--config-file',
            default=os.path.join(os.getcwd(), 'events.conf'),
            help='seafevents config file')

        self._parser.add_argument(
            '--loglevel',
            default='info',
        )

        self._parser.add_argument(
            '-P',
            '--pidfile',
            help='the location of the pidfile'
        )

        self._parser.add_argument(
            '-R',
            '--reconnect',
            action='store_true',
            help='try to reconnect to daemon when disconnected'
        )

def get_ccnet_dir():
    try:
        return os.environ['CCNET_CONF_DIR']
    except KeyError:
        raise RuntimeError('ccnet config dir is not set')

def is_syslog_enabled(config):
    if config.has_option('Syslog', 'enabled'):
        try:
            return config.getboolean('Syslog', 'enabled')
        except ValueError:
            return False
    return False

def main():
    args = AppArgParser().parse_args()
    app_logger = LogConfigurator(args.loglevel, args.logfile) # pylint: disable=W0612
    if args.logfile:
        logdir = os.path.dirname(os.path.realpath(args.logfile))
        os.environ['SEAFEVENTS_LOG_DIR'] = logdir

    os.environ['EVENTS_CONFIG_FILE'] = os.path.expanduser(args.config_file)

    if args.pidfile:
        write_pidfile(args.pidfile)

    config = get_config(args.config_file)
    init_message_handlers()

    if is_syslog_enabled(config):
        app_logger.add_syslog_handler()

    events_listener_enabled = True

    app = App(get_ccnet_dir(), args, events_listener_enabled=events_listener_enabled)

    app.serve_forever()

if __name__ == '__main__':
    main()
