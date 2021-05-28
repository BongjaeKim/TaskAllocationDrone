# -*- coding: utf-8 -*-
"""plz module."""

from __future__ import unicode_literals

import sys
import os
import re
import zipfile

from pyloco.plxtask import PlXTask
from pyloco.task import Task
from pyloco.error import UsageError
from pyloco.util import load_pymod, create_tempdir, pyloco_import

_pat_import = r"^\s*from\s(?P<mod>[\.]?[^\d\W][\.\w]*)\simport\s(?P<cls>[^\d\W]\w*)\sas\sentry_task\s*$"

class PlZTask(Task):
    """PlZ task

        PlZ task run a zipped pyloco package.
    """

    _version_ = "0.1.0"

    def run(self, argv, subargv=None, forward=None):

        if not argv:
            raise UsageError("PlZ Task is not found."
                             " Please check plz path.")

        elif not os.path.isfile(argv[0]):
            raise UsageError("PlZ Task '%s' is not found."
                             " Please check plz path." % str(argv[0]))

        out = -1
        taskpath = argv.pop(0)

        if zipfile.is_zipfile(taskpath):
            tempdir = None

            with create_tempdir() as tempdir:

                plz = zipfile.ZipFile(taskpath)
                plz.extractall(path=tempdir)
                plz.close()
                dirnames = os.listdir(tempdir)

                if len(dirnames) != 1:
                    raise UsageError("'%s' is not a plz file." % taskpath)

                taskname = dirnames[0]
                pkgdir = os.path.join(tempdir, taskname)
                moddir = os.path.join(pkgdir, taskname)

                sys.path.insert(0, pkgdir)
                mod = pyloco_import(taskname)
                taskcls = getattr(mod, "entry_task")
                if taskcls is PlXTask:
                    argv.insert(0, os.path.join(moddir, getattr(mod, "plx")))
                sys.path.pop(0)

                from pyloco.main import perform
                parent = self.get_proxy()

                out = perform(taskcls, argv=argv, subargv=subargv,
                              parent=parent, forward=forward,
                              shared=self.parent.shared) 
            return out

        else:
            raise UsageError("'%s' is not a plz file format." % taskpath)
