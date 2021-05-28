# -*- coding: utf-8 -*-
"""Python Tasking Engine"""

from .util import system, Option            # noqa: F401
from .util import create_tempdir            # noqa: F401
from .main import perform                   # noqa: F401
from .task import Task, taskclass           # noqa: F401
from .grouptask import GroupTask, TaskPath  # noqa: F401
from .grouptask import TaskHub              # noqa: F401
from .manage import Manager, PylocoManager  # noqa: F401
from .manage import collect_mgrattrs        # noqa: F401
from .test import TestCase                  # noqa: F401

__author__ = PylocoManager._author_
__version__ = PylocoManager._version_
