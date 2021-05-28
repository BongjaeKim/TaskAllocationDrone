# -*- coding: utf-8 -*-
"""management task module."""

from __future__ import unicode_literals

import sys
import os
import tempfile
import shutil
import zipfile
import ast
import json
import unittest
import pkg_resources

from pyloco.error import UsageError, InternalError
from pyloco.util import (iterpath, system, urlparse, is_venv, isystem,
                         urlopen, HTTPError, get_pip, pyloco_import,
                         strencode, PY3, OS, import_modulepath, debug)
from pyloco.task import ManagementTask
from pyloco.parse import TestArgParser
from pyloco.test import import_testplx

# NOTE
# To pack properly,
#    a pyloco task to be packed should have dependency to other pyloco tasks
#    in the same module or in the same package. In other words, the task
#    should work if the task is copied to other location. Conventional
#    dependency on Python modules will be discovered by pyloco automatically.

# TODO: support group task to pack

_setup_template = """# -*- coding: utf-8 -*-
"pyloco task setup script"

if __name__ == "__main__":

    from setuptools import setup, find_packages

    __taskname__ = "{taskname}"

    setup(
        name="{distname}",
        version="{version}",
        packages=find_packages(),
        package_data={{{package_data}}},
        install_requires=[{install_requires}],
        entry_points = {{"pyloco.task": [{entry_points}]}},
    )
"""

_init_template = """# -*- coding: utf-8 -*-

from pyloco import Task

class {clsname}(Task):
    "a short task description"

    _name_ = "{taskname}"
    _version_ = "{taskversion}"

    def __init__(self, parent):

        self.add_data_argument("data", type=str, help="input data")

        self.register_forward("data", type=str, help="output data")

    def perform(self, targs):

        output = targs.data

        self.add_forward(data=output)
"""

_taskinit_template = """# -*- coding: utf-8 -*-
# pyloco task package
from %s import %s as entry_task
%s
"""
_taskmain_template = """# -*- coding: utf-8 -*-
#main entry for pyloco command-line interface
from %s import %s as entry_task
from pyloco.main import perform
%s

if __name__ == "__main__":
    import sys
    import multiprocessing
    multiprocessing.freeze_support()

    if "--" in sys.argv:
        idx = sys.argv.index("--")
        perform(entry_task, sys.argv[1:idx], sys.argv[idx+1:])
    else:
        perform(entry_task, sys.argv[1:])
"""


# TODO: use config db
# repo_upload = "" # pypi

# test.pypi.org
#pypi = "https://test.pypi.org"
#repo_upload = "%s/legacy/" % pypi
#repo_install = "%s/simple/" % pypi
#extra_repo_install = "https://pypi.org/simple/"
#repo_check = "%s/pypi" % pypi

# pypi.org
pypi = "https://pypi.org"
repo_upload = "https://upload.pypi.org/legacy/"
repo_install = "%s/simple/" % pypi
extra_repo_install = "https://test.pypi.org/simple/"
repo_check = "%s/pypi" % pypi

class CollectModule(ast.NodeVisitor):

    def __init__(self, modules, cache):
        self.modules = modules
        self.cache = cache

    def _collect_modules(self, name):

        if name in self.cache:
            return

        head = None
        modname = None

        if '.' in name:
            head = name.split(".")[0]
            if not head.startswith("_"):
                modname = head
        elif not name.startswith("_"):
            modname = name

        if modname:
            if modname in sys.modules:
                mod = sys.modules[modname]
                self.modules[modname] = None

            else:
                try:
                    mod = pyloco_import(modname)
                    self.modules[modname] = None

                except Exception:
                    pass

        if head is not None:
            self.cache[head] = None
        self.cache[name] = None

    def visit_Import(self, node):

        for alias in node.names:
            self._collect_modules(alias.name)

    def visit_ImportFrom(self, node):

        if node.level > 0:
            pass
        elif node.module:
            self._collect_modules(node.module)
        else:
            raise Exception("Internal error: unknown ImportFrom syntax: " +
                            str(node))


def collect_modules(path, modules, cache={}):

    # TODO: collect other tasks and data files

    path = os.path.abspath(os.path.realpath(path))

    if path in cache:
        return

    if os.path.isdir(path):
        cache[path] = None

    for pysrc in iterpath(path):
        if pysrc not in cache:
            cache[pysrc] = None
            try:
                with open(pysrc, 'rb') as f:
                    tree = ast.parse(f.read(), filename=pysrc)
                collector = CollectModule(modules, cache)
                collector.visit(tree)
            except SyntaxError:
                pass


class _Pack(object):

    def __init__(self, task, taskpath, distname=None):

        from pyloco.task import load_taskclass

        parent = task.get_proxy()
        argv = task.subargv[1:]

        _dirname, _basename = os.path.split(taskpath)
        _base, _ext = os.path.splitext(_basename)

        # consumes all subargv
        del task.subargv[:]

        task_class, argv, subargv, objs = load_taskclass(taskpath, argv, [])
        if task_class is None:
            raise UsageError("ERROR: Task '%s' is not loaded. "
                             " Please check task-path." % taskpath)

        task = task_class(parent)
        if task is None:
            raise UsageError("ERROR: Task '%s' is not created." % taskpath)

        task._env.update(objs)

        from pyloco.plxtask import PlXTask
        if task_class is PlXTask:
            task._setup(taskpath)

        self.tmpdir = tempfile.mkdtemp()
        self.taskname = task._name_

        topdir = os.path.join(self.tmpdir, self.taskname)
        srcdir = os.path.join(topdir, self.taskname)
        os.makedirs(srcdir)

        package_data = ""

        # generate __init__.py
        if os.path.isfile(taskpath):
            shutil.copy(taskpath, srcdir)

            clsname = task.__class__.__name__

            init_extra = []
            main_extra = []

            if task_class is PlXTask:
                modname = "pyloco.plxtask"
                init_extra.append('plx = "%s"' % _basename)
                main_extra.append('plx = "%s"' % _basename)
                package_data = ('"%s": ["%s"]' %
                    (self.taskname, _basename))
            else:
                modname = "." + _base

                # TODO: add metadata such as __doc__

            with open(os.path.join(srcdir, "__init__.py"), "w") as f:
                extra = "\n".join(init_extra)
                f.write(_taskinit_template % (modname, clsname, extra))

            with open(os.path.join(srcdir, "__main__.py"), "w") as f:
                extra = "\n".join(main_extra)
                f.write(_taskmain_template % (modname, clsname, extra))

        elif os.path.isdir(taskpath):
            import pdb; pdb.set_trace()     # noqa: E702
        else:
            raise UsageError(
                "Task '%s' supports packing of Python module and package." %
                self.taskname
            )

        setup_kwargs = {}
        modules = {}
        mod2dist = {}
        dists = {}

        collect_modules(srcdir, modules)

        ret, sout, serr = system("pip list")
        sout = sout.replace("(", " ").replace(")", " ")
        dist_list = [d.split() for d in sout.split("\n")[2:] if d]

        for d, v in dict(d for d in dist_list if len(d) == 2).items():
            ret, sout, serr = system("pip show -f " + d)

            for line in sout.split("\n"):
                if line.endswith("__init__.py"):
                    pkgline = line.split(os.sep)

                    if len(pkgline) == 2:
                        mod2dist[pkgline[0].strip()] = (d, v)
                elif line.strip() == d + ".py":
                    mod2dist[d] = (d, v)

        site = os.path.dirname(ast.__file__)

        for m, v in modules.items():
            d = mod2dist.get(m, None)

            if m == "pyloco":
                from pyloco.manage import PylocoManager
                dists[m] = PylocoManager._version_

            elif m == parent.get_managerattr("name"):
                dists[m] = parent.get_managerattr("version")

            elif d is None:
                d = sys.modules.get(m, None)

                if m in sys.builtin_module_names:
                    pass

                else:
                    pass
                    # TODO: check this
#                    moddir = os.path.dirname(d.__file__)
#                    sitem = os.path.join(site, m)
#
#                    if moddir != site and moddir != sitem: 
#                        import pdb; pdb.set_trace()
#                        raise InternalError(
#                            "Distribution package for '%s' module is not "
#                            "found." % m)
            else:
                dists[d[0]] = d[1]
            
        # TODO: copy other tasks and data files in srcdir

        install_requires = []

        if hasattr(task, "_install_requires_"):
            install_requires.extend(['"%s"' % r for r in task._install_requires_])

        for dname, dver in dists.items():
            if dver is not None:
                install_requires.append('"{0}>={1}"'.format(dname, dver))
            else:
                install_requires.append('"{}"'.format(dname))
        setup_kwargs["install_requires"] = ", ".join(install_requires)

        # generate setup.py
        with open(os.path.join(topdir, "setup.py"), "w") as f:
            setup_kwargs["distname"] = distname if distname else self.taskname
            setup_kwargs["taskname"] = self.taskname
            setup_kwargs["version"] = getattr(task, "_version_", "0.1.0")
            setup_kwargs["package_data"] = package_data
            setup_kwargs["entry_points"] = (
                '"{taskname} = {taskname}:entry_task".format(taskname=__taskname__)'
            )
            f.write(_setup_template.format(**setup_kwargs))

    def __enter__(self):
        return self.taskname, self.tmpdir

    def __exit__(self, type, value, traceback):
        if self.tmpdir:
            shutil.rmtree(self.tmpdir)


class _Unpack(object):

    def __init__(self, zfile):

        self.tmpdir = tempfile.mkdtemp()
        shutil.unpack_archive(zfile, self.tmpdir, "zip")
        dirnames = os.listdir(self.tmpdir)
        if len(dirnames) != 1:
            raise UsageError("'%s' is not a plz file." % zfile)
        self.taskname = dirnames[0]

    def __enter__(self):
        return self.taskname, self.tmpdir

    def __exit__(self, type, value, traceback):
        if self.tmpdir:
            shutil.rmtree(self.tmpdir)


class CliAppTask(ManagementTask):
    """create a command line interface to a pyloco task

'cliapp' task creates a shell script or a development setup for a
shell script that lanuches a pyloco task.
"""

    _version_ = "0.1.0"
    _name_ = "cliapp"

    def __init__(self, parent):

        self.add_data_argument("command", type=str, required=True,
                               help="command path")

    def perform(self, targs):

        if os.path.exists(targs.command):
            raise UsageError("Specified command '%s' already exists." %
                             targs.command)

        # get OS and select shell script type
        if OS == "windows":
            import pdb; pdb.set_trace()

        else:
            if len(self.subargv) < 1:
                raise UsageError("No target task is specified.")

            if not os.path.exists(self.subargv[0]):
                raise UsageError("Target task does not exist: %s" % self.subargv[0])

            self.subargv[0] = os.path.abspath(os.path.realpath(self.subargv[0]))

            with open(targs.command, "w") as f:
                retval, stdout, _ = system("which bash")
                if retval == 0:
                    f.write("#!" + stdout + "\n")
                    f.write("%s %s $*" % (sys.argv[0], " ".join(self.subargv)))
            os.chmod(targs.command, 0o744)


class InitTask(ManagementTask):
    """create a base code of pyloco task

'init' task creates a base code for a new pyloco task.
The type of task is decided according to file extension specified
in command line.

    * <taskname>.py  : a task in a single file
    * <taskname>.plx : a plx task in a single file
    * <taskname>     : a task as a Python package

"""

    _version_ = "0.1.0"
    _name_ = "init"

    def __init__(self, parent):

        self.add_data_argument("task", type=str, required=True,
                               help="setup initial task")

        self.add_option_argument("-v", "--task-version", type=str,
                                 default="0.1.0", help="task version")

    def perform(self, targs):

        if os.path.exists(targs.task):
            raise UsageError("Task '%s' is already exists: " % targs.task)

        outdir, filename = os.path.split(targs.task)
        outdir = os.path.abspath(outdir)

        if not os.path.exists(outdir):
            os.makedirs(outdir)

        taskname, tasktype = os.path.splitext(filename)
        if not taskname and tasktype:
            taskname = tasktype
            tasktype = "package"

        clsname = taskname[0].upper() + taskname[1:]

        if tasktype == ".py":
            output = _init_template.format(clsname=clsname, taskname=taskname,
                                           taskversion=targs.task_version)

            with open(targs.task, "w") as f:
                f.write(output)

        elif tasktype == ".plx":
            import pdb; pdb.set_trace()

        elif tasktype == "package":
            import pdb; pdb.set_trace()

        else:
            raise UsageError("Unknown task type: %s" % tasktype)

        print("Initialized '%s' task development in '%s'" %
              (taskname, outdir))

class UninstallTask(ManagementTask):
    """uninstall a pyloco task

'uninstall' task removes a pyloco task from local system.
"""

    _version_ = "0.1.0"
    _name_ = "uninstall"

    def __init__(self, parent):

        self.add_data_argument('task', type=str, nargs="*", required=False,
                               help='task to uninstall')

    def perform(self, targs):

        if targs.task:
            if len(targs.task) > 1:
                raise UsageError(
                    "'uninstall' task only one task: %s." % targs.task
                )

            taskname = targs.task[0]

        elif self.subargv:
            if "--" in self.subargv:
                raise UsageError(
                    "'uninstall' task requires only one sub-task "
                    "to uninstall, but found multiple sub-tasks: '%s'" %
                    " ".join(self.subargv)
                )

            taskname = self.subargv[0]
            del self.subargv[:]

        else:
            raise UsageError(
                "'uninstall' task requires one sub-task to uninstall."
            )

        for ep in pkg_resources.iter_entry_points(group='pyloco.task'):
            if ep.name == taskname:
                retval, sout, serr = system(
                    get_pip() + " uninstall -y " + ep.dist.project_name
                )

                if retval == 0:
                    print("'%s' task is uninstalled successfully." % taskname)

                else:
                    print("Uninstallation of '%s' task was failed: %s" %
                          (taskname, serr))

                return retval

        raise UsageError("'%s' is not found." % taskname)


class InstallTask(ManagementTask):
    """install a pyloco task on a local computer

'install' task installs a pyloco task in local system. 'install' is
one of pyloco bulit-in tasks.
"""

    _version_ = "0.1.0"
    _name_ = "install"

    def __init__(self, parent):

        self.add_data_argument('task', type=str, nargs="?", required=False,
                               help='task to install')

        self.add_option_argument(
            "-n", "--name", help="task install name"
        )
        self.add_option_argument(
            "--user", action="store_true",
            help="install a task in user's space."
            " Only works on installing from pypi"
        )
        self.add_option_argument(
            "-U", "--upgrade", action="store_true",
            help="upgrade a task"
        )

    def _install(self, topdir, taskname, targs):

        dirnames = os.listdir(topdir)

        if "setup.py" not in dirnames:
            raise UsageError("'setup.py' is not found.'")

        if targs.name and targs.name != taskname:
            new_taskname = targs.name
            os.rename(os.path.join(topdir, taskname),
                      os.path.join(topdir, new_taskname))
            taskname = new_taskname
            setup = os.path.join(topdir, "setup.py")
            oldsetup = os.path.join(topdir, "setup.py.old")
            shutil.move(setup, oldsetup)
            prefix = '    __taskname__ = "'
            with open(setup, "w") as fw:
                with open(oldsetup, "r") as fr:
                    for line in fr:
                        if line.startswith(prefix):
                            fw.write(prefix+taskname+'"\n')
                        else:
                            fw.write(line)
            os.remove(oldsetup)

        retval, stdout, stderr = system(
            sys.executable + " setup.py sdist" " --formats=tar", cwd=topdir
        )

        if retval != 0:
            raise InternalError(stderr)

        distdir = os.path.join(topdir, "dist")
        sdist = None

        for dname in os.listdir(distdir):
            if dname.endswith(".tar"):
                sdist = dname
                break

        if sdist is None:
            raise InternalError(
                "'sdist' file is not found: %s" % taskname
            )

        if is_venv():
            retval, stdout, stderr = system(
                get_pip() + " install " + sdist, cwd=distdir
            )
            # system("python setup.py install", cwd=topdir)
        else:
            retval, stdout, stderr = system(
                get_pip() + " install %s --user" % sdist, cwd=distdir
            )
            # system("python setup.py install --user", cwd=topdir)

        if retval == 0:
            # TODO: print installed version with some progress remarks
            print("'%s' task is installed successfully." % taskname)

        else:
            raise InternalError(stderr)

    def perform(self, targs):

        if targs.task:
            taskpath = targs.task

        elif self.subargv:
            if "--" in self.subargv:
                raise UsageError(
                    "'install' task requires only one sub-task "
                    "to install, but found multiple sub-tasks: '%s'" %
                    " ".join(self.subargv)
                )

            taskpath = self.subargv[0]

        else:
            raise UsageError(
                "'install' task requires one sub-task to install."
            )

        if os.path.exists(taskpath):

            if zipfile.is_zipfile(taskpath):
                if taskpath.endswith(".plz"):

                    with _Unpack(taskpath) as (taskname, tmpdir):
                        topdir = os.path.join(tmpdir, taskname)
                        dirnames = os.listdir(topdir)

                        if taskname not in dirnames:
                            raise UsageError(
                                "'%s' is not a plz file." % taskpath
                            )

                        self._install(topdir, taskname, targs)
                else:
                    raise UsageError("Unknown file format: %s" % taskpath)
            else:
                with _Pack(self, taskpath) as (taskname, tmpdir):
                    topdir = os.path.join(tmpdir, taskname)
                    self._install(topdir, taskname, targs)
        else:

            # TODO?: ask user permission to install

            installed = False

            try:
                distname = taskpath.replace("_", "-")
                url = "%s/%s/json" % (repo_check, distname)

                if not PY3:
                    url = strencode(url)

                if json.load(urlopen(url)):
                    prefix = (" install -i %s --extra-index-url %s " %
                              (repo_install, extra_repo_install))
                    args = []

                    if targs.user or not (is_venv() or "CONDA_DEFAULT_ENV" in os.environ):
                        args.append("--user")

                    if targs.upgrade:
                        args.append("-U")

                    ret, _, _ = system(get_pip() + prefix + " ".join(args) +
                                       " " + distname)

                    if ret == 0:
                        print("'%s' task is installed successfully." % taskpath)
                        installed = True

            except HTTPError:
                pass

            if not installed:
                url = urlparse(taskpath)

                if url.netloc or url.scheme:
                    import pdb; pdb.set_trace()     # noqa: E702

                else:
                    raise UsageError("Task '%s' is not found." % taskpath)

        del self.subargv[:]


class TestTask(ManagementTask):
    """test a pyloco task

'test' task perform unittest on a pyloco task.
"""

    _version_ = "0.1.0"
    _name_ = "test"

    def __new__(cls, *vargs, **kwargs):

        cls.original_argparser = ManagementTask._argparser_
        ManagementTask._argparser_ = TestArgParser

        return super(TestTask, cls).__new__(cls, *vargs, **kwargs)

    def __init__(self, parent):

        self.set_data_argument('test', type=str, required=False,
                               help='unittests')

        self.add_option_argument(
            "-a", "--testargv", action="append", help="test arguments"
        )

        self.add_option_argument(
            "-s", "--testsubtask", action="append", help="test subtasks"
        )

        #self.add_option_argument("-o", "--outdir", help="output directory")

    def perform(self, targs):

        try:
            #original_argparser = Task._argparser_
            #Task._argparser_ = TestArgParser

            if targs.test:

                if targs.test.endswith(".plx"):
                    module = import_testplx(targs.test, self.get_proxy(),
                            targs.testargv, targs.testsubtask)

                else:
                    _, module = import_modulepath(targs.test)

                unittest.main(module=module, argv=["dummy"])

            elif self.subargv:
                import pyloco.grouptask as testmodule
                del testmodule.DefaultGroupTestCase._testargs_[:]
                testmodule.DefaultGroupTestCase._testargs_.extend(self.subargv)
                unittest.main(module=testmodule, argv=["dummy"])

            else:
                raise UsageError("No test is specified.")
#
#
#            results = []
#
#            # invoke test runner
#            if targs.params:
#                for param in targs.params:
#                    for varg in param.vargs:
#                        results.append((vargs, param.kwargs, tester.run(varg, param.kwargs)))
#

        finally:
            ManagementTask._argparser_ = self.original_argparser


class PackTask(ManagementTask):
    """pack a pyloco task

'pack' task collects a pyloco task defined in a python module file
or multiple python module files in a python package into a zipped file.
"""

    _version_ = "0.1.0"
    _name_ = "pack"

    def __init__(self, parent):

        self.add_data_argument('task', type=str, nargs="?", required=False,
                               help='task to pack')

        self.add_option_argument(
            "-n", "--name", help="plz-file name [default=<taskname>.plz]"
        )
        self.add_option_argument("-o", "--outdir", help="output directory")

    def perform(self, targs):

        if targs.task:
            taskpath = targs.task

        elif self.subargv:
            if "--" in self.subargv:
                raise UsageError(
                    "'upload' task requires only one sub-task "
                    "to upload, but found multiple sub-tasks: '%s'" %
                    " ".join(self.subargv)
                )

            taskpath = self.subargv[0]

        else:
            raise UsageError(
                "'upload' task requires one sub-task to upload."
            )

        with _Pack(self, taskpath, distname=targs.name) as (taskname, tmpdir):
            topdir = os.path.join(tmpdir, taskname)
            outdir = targs.outdir if targs.outdir else ""

            if targs.name:
                outfile = os.path.join(outdir, targs.name+".plz")

            else:
                outfile = os.path.join(outdir, taskname+".plz")

            shutil.make_archive(topdir, 'zip', *os.path.split(topdir))
            shutil.move(topdir+".zip", outfile)

            print("'%s' task is packed successfully." % taskpath)


class UploadTask(ManagementTask):
    """upload a pyloco task to pyloco index server

'upload' task collects a pyloco task defined in a python module file
or multiple python module files in a python package and upload to
pyloco index server.
"""

    _version_ = "0.1.0"
    _name_ = "upload"

    def __init__(self, parent):

        self.add_data_argument('task', type=str, nargs="?", required=False,
                               help='task to upload to index server')

        self.add_option_argument(
            "-n", "--name", help="distribution package name [default=<taskname>]"
        )
        self.add_option_argument(
            "-r", "--repository", type=str, default=repo_upload,
            help="url of repository [default: %s]" % repo_upload
        )

    def perform(self, targs):

        if targs.task:
            taskpath = targs.task

        elif self.subargv:
            if "--" in self.subargv:
                raise UsageError(
                    "'upload' task requires only one sub-task "
                    "to upload, but found multiple sub-tasks: '%s'" %
                    " ".join(self.subargv)
                )

            taskpath = self.subargv[0]

        else:
            raise UsageError(
                "'upload' task requires one sub-task to upload."
            )

        with _Pack(self, taskpath, distname=targs.name) as (taskname, tmpdir):
            cwd = os.getcwd()
            os.chdir(os.path.join(tmpdir, taskname))
            ret, sout, serr = system(sys.executable + " setup.py sdist")
            ret, sout, serr = system(sys.executable + " setup.py bdist_wheel --universal")
            ret = isystem("twine upload --repository-url %s dist/*" %
                          targs.repository)
            os.chdir(cwd)

            if ret == 0:
                print("'%s' task is uploaded successfully." % taskpath)

            else:
                print("Uploading of '%s' task is failed." % taskpath)


mgmt_tasks = {
        "cliapp":           CliAppTask,
        "init":             InitTask,
        "test":             TestTask,
        "install":          InstallTask,
        "uninstall":        UninstallTask,
        "pack":             PackTask,
        "upload":           UploadTask,
    }
