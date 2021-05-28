# -*- coding: utf-8 -*-
"""proxy module."""

import copy

from pyloco.error import UsageError
from pyloco.base import pyloco_builtins


class Proxy(object):

    def __init__(self, task, shared=None):

        self.task = task
        self.shared = shared if isinstance(shared, dict) else {}

        if "parent_name" not in self.shared:
            self.shared["parent_name"] = "%s.%s" % (
                self.task.parent.shared["parent_name"], self.task._name_)

    def __copy__(self):

        return self.__class__(self.task, copy.copy(self.shared))

    def __deepcopy__(self, memo):

        return self.__class__(self.task, copy.deepcopy(self.shared))


class ParentProxy(Proxy):

    def __getattr__(self, attr):

        if attr in ("log_setup", "get_managerattr"):
            return getattr(self.task.parent, attr)

        if attr == "_logger":
            return (self.task._logger if self.task._logger else
                    getattr(self.task.parent, attr))

        raise AttributeError("'ParentProxy' object has no attribute '%s'" %
                             attr)


