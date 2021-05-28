# -*- coding: utf-8 -*-
"""test module."""

from __future__ import unicode_literals

import os
import unittest
import pydoc
from functools import partial

from pyloco.util import load_pymod, debug, parse_param_option
from pyloco.plxtask import PlXTask
from pyloco.base import pyloco_builtins
from pyloco.error import UsageError

def load_testclass(testpath):

    if not testpath:
        return None

    if isinstance(testpath, type):
        if issubclass(testpath, Test):
            return testpath
        raise UsageError("Not compatible test type: %s" % type(testpath))

    test_class = None

    _p = testpath.split("#", 1)

    if len(_p) == 2:
        testpath, fragment = [x.strip() for x in _p]

    else:
        fragment = ""

    if os.path.exists(testpath):

        mods = []

        if os.path.isfile(testpath):
            head, base = os.path.split(testpath)

            if base.endswith(".py"):
                mods.append(load_pymod(head, base[:-3]))

        candidates = {}

        for mod in mods:
            for name in dir(mod):
                if not name.startswith("_"):
                    obj = getattr(mod, name)

                    if (type(obj) == type(Test) and issubclass(obj, Test) and
                            (obj.__module__ is None or
                                not obj.__module__.startswith("pyloco."))):
                       candidates[name] = obj
        if candidates:
            if fragment:
                if hasattr(candidates, fragment):
                    test_class = getattr(candidates, fragment)

                else:
                    raise UsageError("No test is found with a fragment of "
                                     "'%s'." % fragment)
            elif len(candidates) == 1:
                test_class = candidates.popitem()[1]

            else:
                raise UsageError(
                    "More than one frame are found."
                    "Please add fragment to select one: %s" %
                    list(candidates.keys())
                )

        if test_class:
            setattr(test_class, "_path_", os.path.abspath(testpath))

        else:
            raise UsageError("Test class is not found. Please check path: %s" % testpath)

    return test_class


class TestCase(unittest.TestCase):
    """pyloco TestCase

"""

    def perform_test(self, task, *vargs, **kwargs):

        from pyloco.main import perform

        if vargs:
            return perform(task, list(vargs), **kwargs)

        else:
            return perform(task, **kwargs)


class TestSuite(unittest.TestSuite):

    def run(self, *vargs, **kwargs):

        from pyloco.task import Task
        from pyloco.parse import TestArgParser

        try:
            original_argparser = Task._argparser_
            Task._argparser_ = TestArgParser

            return super(TestSuite, self).run(*vargs, **kwargs)

        finally:
            Task._argparser_ = original_argparser


class PlXTestTask(PlXTask):

    def perform(self, targs):

        for plx_dest, opt in self.plx_argdefs.items():
            dest = opt.kwargs.get("dest", opt.vargs[0])
            if dest in self._env["__arguments__"]:
                argval = self._env["__arguments__"].pop(dest, None)
                self._env["__arguments__"][plx_dest] = argval

        return self.run_section(self.plx_entry_body)

    def test_section(self, hdr, body):

        # check hdr
        if hdr.endswith("*"):
            special_sec = True
            opt = parse_param_option(hdr[:-1], False,
                                     self.parent.shared)
        else:
            special_sec = False
            opt = parse_param_option(hdr, False, self.parent.shared)

        env = dict(self.parent.shared)
        env["__builtins__"] = pyloco_builtins
        sec_check = all([eval(c, env) for c in opt.context])

        if sec_check:
            sec_name = opt.vargs[0]

            # find sec_handler
            if special_sec:
                if sec_name in self._section_handlers:
                    sec_handler = self._section_handlers[sec_name]

                else:
                    raise UsageError(
                        "Special section '%s' is not registered."
                        " Please register first." % sec_name
                    )
            else:
                sec_handler = self.run_section

            return sec_handler(body, *opt.vargs[1:], **opt.kwargs)

        else:

            return 0

class PlXTest(TestCase):

    _setups = []
    _teardowns = []

    def setUp(self):
        for setup in self._setups:
            setup()

    def tearDown(self):
        for teardown in self._teardowns:
            teardown()

    @classmethod
    def _test_template(self, header=None, body=None):
        if header and body:
            assert self._plx_.test_section(header, body) == 0


def import_testplx(path, manager, argv, subargv):

    if argv is None:
        argv = []

    if subargv is None:
        subargv = []

    if not os.path.isfile(path):
        raise UsageError("PlX Task '%s' is not found."
                         " Please check plx path." % str(path))

    PlXTest._plx_ = plx = PlXTestTask(manager)
    plx._setup(path)

    prog = os.path.basename(getattr(plx, "_path_", plx._name_))
    plx._parser.prog = plx.get_mgrname() + " " + prog[-20:]

    if hasattr(plx, "__doc__") and plx.__doc__:
        plx._parser.desc, plx._parser.long_desc = pydoc.splitdoc(
                                                    plx.__doc__)
    super(PlXTask, plx).run(argv, subargv=subargv)

    del PlXTest._setups[:]
    del PlXTest._teardowns[:]

    # create  test methods
    for hdr, body in plx.plx_sections:
        if hdr.endswith("*"):
            if hdr.startswith("setup"):
                PlXTest._setups.append(partial(PlXTest._test_template, header=hdr[:-1], body=body))
            elif hdr.startswith("teardown"):
                PlXTest._teardowns.append(partial(PlXTest._test_template, header=hdr[:-1], body=body))

        else:
            setattr(PlXTest, "test_%s" % hdr.replace("@", "_"),
                    partial(PlXTest._test_template, header=hdr, body=body))

    import imp
    mod = imp.new_module("")

    setattr(mod, "PlXTest", PlXTest)

    return mod
