from __future__ import print_function, absolute_import

import threading
from datetime import datetime

import sublime
import sublime_plugin

from imp import load_source
from os.path import join
from sys import path

try:
    from .utils import log, log_exc, SETTINGS_FILE, PROJECT_ROOT
except (ValueError, SystemError):
    from utils import log, log_exc, SETTINGS_FILE, PROJECT_ROOT

try:
    import queue
except ImportError:
    import Queue as queue

if PROJECT_ROOT not in path:
    path.append(PROJECT_ROOT)

CHAR_KEY_PREFIX = 'char'
THREAD_TIMEOUT = 30


class StatsSender(threading.Thread):

    def __init__(self, queue, *args, **kwds):
        super(StatsSender, self).__init__(*args, **kwds)
        settings = sublime.load_settings(SETTINGS_FILE)
        sender = settings.get('sender')
        endpoint = settings.get("%s_endpoint" % sender)
        sender_module = load_source('sender', join(PROJECT_ROOT, 'senders',
                                                 '%s_sender.py' % (sender,)))

        self.sender = sender_module.Sender(endpoint)
        self.queue = queue
 
    def _get_data(self):
        try:
            data = self.queue.get(True, THREAD_TIMEOUT)
        except queue.Empty:
            data = None
        return data

    def run(self):
        data = self._get_data()
        while data is not None:
            if self.sender is not None:
                try:
                    self.sender.send(data)
                except Exception as e:
                    log_exc("Exception on send method")
            data = self._get_data()
        log("Terminating", threading.current_thread())


class DevTrackListener(sublime_plugin.EventListener):

    def __init__(self, *args, **kwargs):
        super(DevTrackListener, self).__init__(*args, **kwargs)
        self.communication_queue = queue.Queue()
        self.active_thread = None

    def on_query_context(self, view, key, operator, operand, match_all):
        data = self._format_data(view, key, operand)
        self._send_data(data)
        return None

    def _check_thread(self):
        if self.active_thread is None or not self.active_thread.is_alive():
            self.active_thread = StatsSender(self.communication_queue)
            self.active_thread.start()
            log("Starting", self.active_thread)

    def _send_data(self, data):
        if data is not None:
            self._check_thread()
            self.communication_queue.put(data)

    def _format_data(self, view, key, operand):
        data = None
        filename = view.file_name()
        if key.endswith('_keypress') and filename is not None:
            keypress_type, _ = key.split('_')

            data = dict(
                filename=filename,
                key=operand if keypress_type != CHAR_KEY_PREFIX else CHAR_KEY_PREFIX,
                timestamp=datetime.utcnow()
            )

        return data


class DevTrackCommand(sublime_plugin.TextCommand):

    def run(self, edit, key, command=None, args=None):
        pass
