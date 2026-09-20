"""Nonblocking JSONL commands, polled only at safe trainer boundaries.

Windows worker spawning must not race a blocking buffered stdin reader.
"""
import os
import sys
import json


class CommandInbox:
    def __init__(self):
        self.buffer = b''

    def feed(self, data):
        self.buffer += data
        if len(self.buffer) > 65536:
            self.buffer = b''
            raise ValueError('Command exceeds 64 KiB')
        messages = []
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            try:
                message = json.loads(line.decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.buffer = b''
                raise ValueError('Invalid command payload') from exc
            if not isinstance(message, dict) or message.get('schema_version') != 1:
                self.buffer = b''
                raise ValueError('Unsupported command schema')
            if message.get('command') not in ('pause', 'stop', 'reset'):
                self.buffer = b''
                raise ValueError('Unknown command')
            messages.append(message['command'])
        return messages

    def poll(self):
        try:
            fd = sys.stdin.fileno()
            if os.name == 'nt':
                import ctypes
                import msvcrt
                available = ctypes.c_ulong()
                peek = ctypes.windll.kernel32.PeekNamedPipe
                peek.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong,
                                 ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p]
                peek.restype = ctypes.c_int
                if not peek(msvcrt.get_osfhandle(fd), None, 0, None, ctypes.byref(available), None):
                    return []
                size = min(available.value, 4096)
            else:
                import select
                size = 4096 if select.select([fd], [], [], 0)[0] else 0
            return self.feed(os.read(fd, size)) if size else []
        except (OSError, AttributeError):
            return []
