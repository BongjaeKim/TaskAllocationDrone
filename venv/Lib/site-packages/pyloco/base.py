# -*- coding: utf-8 -*-
"""base object module."""

from __future__ import unicode_literals

import abc
import threading

from pyloco.util import PY3

exclude_list = ["exec", "eval"]

pyloco_builtins = dict((k, v) for k, v in __builtins__.items()
                       if k not in exclude_list)

# TODO: add _hash_, _iid_, _gid_ to Object

if PY3:
    Object = abc.ABCMeta("Object", (object,), {})
else:
    Object = abc.ABCMeta("Object".encode("utf-8"), (object,), {})


class Global(object):

    _attrs = {}

    def __setattr__(self, name, value):

       with threading.Lock():
            self._attrs[name] = value

    def __getattr__(self, name):
        return self._attrs[name]

del PY3
del exclude_list
