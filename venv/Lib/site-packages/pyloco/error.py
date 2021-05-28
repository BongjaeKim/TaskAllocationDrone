# -*- coding: utf-8 -*-
"""error module."""

from __future__ import unicode_literals


class TaskError(Exception):

    def __init__(self, msg, **kwargs):

        super(TaskError, self).__init__(msg)


class NormalExit(TaskError):

    def __init__(self, **kwargs):
        super(NormalExit, self).__init__("", **kwargs)


class UsageError(TaskError):
    pass


class InternalError(TaskError):
    pass


class TestError(TaskError):
    pass


class ConfigError(TaskError):
    pass


class TypeCheckError(TaskError):

    def __init__(self, value, expected_type):

        msg = ('type of "%s" is "%s", but expected "%s"' %
               (str(value), type(value), expected_type))
        super(TypeCheckError, self).__init__(msg)


class UnknownNameError(TaskError):
    pass
