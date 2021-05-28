# -*- coding: utf-8 -*-
"""standard task module."""

from __future__ import unicode_literals

import os
import pydoc
import string
import docutils.nodes
import docutils.parsers.rst
import docutils.utils
from docutils.core import publish_from_doctree, publish_string

from pyloco.task import StandardTask, load_taskclass
from pyloco.util import split_docsection
from pyloco.error import UsageError

from docutils.core import publish_doctree
from docutils.nodes import paragraph, section

readme_template = """
===============================================================
__{name}__ __{type}__
===============================================================

version: __{version}__

__{short description}__

__{long description}__

Installation
-------------

__{installation}__

Usage
-------------

__{usage}__

Contributing
-------------

__{contributing}__

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

License
-------------

__{license}__
"""

def _lowerstrip(s):
    return "".join(s.replace("_", "").split()).lower()

class PartialFormatter(string.Formatter):

    def __init__(self):
        self.missing_field = ""
        self.bad_format = "[[Formatting failed]]"

    def get_field(self, field_name, args, kwargs):

        name = _lowerstrip(field_name) 

        try:
            val=super(PartialFormatter, self).get_field(name, args, kwargs)

        except (KeyError, AttributeError):
            self.missing_field = "[['%s' field is not available]]" % field_name
            val=None, field_name

        return val 

    def format_field(self, value, spec):

        if value==None:
            return self.missing_field

        try:
            return super(PartialFormatter, self).format_field(value, spec)

        except ValueError:
            return self.bad_format  

#StdoutDefaultTemplate = """
#===================
#First section
#===================
#
#==========
#Sec2
#==========
#"""
#ReadmeDefaultTemplate = """
#===================
#First section
#===================
#
#==========
#Sec2
#==========
#"""
#
#
#_default_title = "{task_name} task"
#_default_oneliner = ("{task_name} is a command-line program that runs on "
#                     "pyloco framework.")
#_default_description = ""
#_default_installation = """
#Installation
#------------
#
#To install {task_name} task, run the following pyloco command. ::
#
#    >>> pyloco install {task_path}
#    >>> pyloco {task_path} --version
#    {task_name} {task_version}
#
#If pyloco is not available on your computer, please run the following
#command to install pyloco, and try again above task installation. ::
#
#    >>> pip install pyloco --user
#    >>> pyloco --version
#    pyloco {manager_version}
#
#.. note::
#
#    - 'pip' is a Python package manager.
#    - Remove '--user' option to run pyloco on a virtual environment.
#    - Add '-U' option to 'pip' command to upgrade pyloco.
#    - We recommend to use pyloco version {manager_version} or higher.
#"""
#
#
#def parse_rst(text):
#    parser = docutils.parsers.rst.Parser()
#    components = (docutils.parsers.rst.Parser,)
#    settings = docutils.frontend.OptionParser(components=components).get_default_values()
#    document = docutils.utils.new_document('<rst-doc>', settings=settings)
#    parser.parse(text, document)
#    return document
#
#
#class RSTVisitor(docutils.nodes.NodeVisitor):
#
#    def unknown_visit(self, node):
#        pass
#
#class TopSections(RSTVisitor):
#
#    def visit_document(self, node):
#
#        self.sections = {}
#
#        for child in node.children:
#            if isinstance(child, docutils.nodes.section):
#                # TODO: parse section
#                for name in child["names"]:
#                    self.sections[name] = child
#
#class Sections(RSTVisitor):
#
#    def __init__(self, *vargs, **kwargs):
#
#        super(Sections, self).__init__(*vargs, **kwargs)
#
#        self.sections = {}
#
#    def visit_section(self, node):
#
#        for name in node["names"]:
#            self.sections[name] = (node.parent, node.parent.children.index(node))
#
#
#class HelperBase(object):
#
#    def __init__(self, task, targs):
#        self.task = task
#        self.targs = targs
#        self.sections = None
#
#    def _generate(self, template):
#
#        # TODO template common tasks
#
#        # parse template with rst
#
#        # parse doc with rst
#
#        # apply docrst to template rst
#
#        temp = parse_rst(template)
#        secs = Sections(temp)
#        temp.walk(secs)
#
#        doc = parse_rst(getattr(self.task, "__doc__", ""))
#        topsecs = TopSections(doc)
#        doc.walk(topsecs)
#        self.sections = topsecs.sections
#
#        for name, (parent, idx) in  secs.sections.items():
#            if name in topsecs.sections:
#                parent.children[idx] = topsecs.sections[name]
#
#
#        #out = publish_from_doctree(temp, writer_name="rst")
#        #out = publish_from_doctree(temp)
#        import pdb; pdb.set_trace()
#        self.generate()
#
#    def generate(self):
#        raise NotImplementedError("'%s' should implement 'generate' method." %
#                             self.__class__.__name__ )
#
#class ReadmeHelper(HelperBase):
#
#    def generate(self):
#        import pdb ; pdb.set_trace()
#
#class StdoutHelper(HelperBase):
#
#    def generate(self):
#        import pdb ; pdb.set_trace()
#
#    def pyloco_help(self, task, targs):
#
#        from pyloco.mgmttask import mgmt_tasks
#        from pyloco.stdtask import standard_tasks
#
#        task_path = os.path.basename(getattr(task, "_path_", task._name_))
#
#        strmap = {
#            "task_name": task._name_,
#            "task_path": task_path,
#            "task_version": task._version_,
#            "manager_version": task.parent.get_managerattr("version"),
#        }
#
#        lines = []
#
#        #### head ####
#        if targs.headnote:
#            lines.append(targs.headnote)
#
#        #### title ####
#
#        if targs.title is None:
#            title = _default_title.format(**strmap)
#        else:
#            title = targs.title.format(**strmap)
#
#        lines.append("=" * len(title))
#        lines.append(title)
#        lines.append("=" * len(title) + "\n")
#        lines.append("version: {task_version}\n".format(**strmap))
#
#        #### one-liner and long description and sections ####
#
#        if task.__doc__:
#            oneliner, remained = pydoc.splitdoc(task.__doc__)
#            description, sections = split_docsection(remained)
#
#        else:
#            oneliner, description, sections = None, "", []
#
#        if targs.oneliner is not None:
#            oneliner = targs.oneliner.format(**strmap)
#
#        elif not oneliner:
#            oneliner = _default_oneliner.format(**strmap)
#
#        if oneliner:
#            lines.append(oneliner +"\n")
#
#
#        if targs.description is not None:
#            description = targs.description.format(**strmap)
#
#        elif not description:
#            description = _default_description.format(**strmap)
#
#        if description:
#            lines.append(description + "\n")
#
#        if targs.installation is None:
#            installation = _default_installation.format(**strmap)
#
#        elif (task.__class__ in mgmt_tasks.values() or
#                task.__class__ in standard_tasks.values()):
#            installation = None
#
#        else:
#            installation = targs.installation.format(**strmap)
#
#        
#        if installation and targs.add and "installation" in targs.add:
#            lines.append(installation)
#
#        if targs.usage is not None:
#            lines.append(targs.usage)
#
#        else:
#            cmdline = "Command-line syntax"
#            lines.append(cmdline)
#            lines.append("-" * len(cmdline) + "\n")
#
#            helplines = task._parser.generate_help("-h")
#            lines.append("".join(helplines))
#            lines.append("\n")
#
#        if targs.section is not None:
#            lines.extend(targs.sections)
#
#        else:
#            lines.extend(sections)
#
#        #### footnote ####
#        if targs.footnote:
#            lines.append(targs.footnote)
#
#        outtext = "\n".join(lines)
#
#        outfile = None
#
#        if targs.output.endswith(".rst"):
#            outfile = targs.output
#            output = "rst"
#        elif targs.output.endswith(".htm") or targs.output.endswith(".html"):
#            outfile = targs.output
#            output = "html"
#        else:
#            output = "pydoc"
#
#        if output == "pydoc":
#            pydoc.pager(outtext)
#            return
#
#        if output == "rst":
#            with open(outfile, "w") as f:
#                f.write("..  -*- coding: utf-8 -*-\n\n")
#                f.write(outtext)
#            return
#
#        if output == "html":
#            # TODO: load sphinx and generate html
#            raise NotImplementedError("html support in help task")
#
#        if output == "web":
#            # TODO: load sphinx and generate html
#            # TODO: connect to helptask webapp
#            raise NotImplementedError("web support in help task")
#
#_helpers = {
#    "stdout": StdoutHelper,
#    "readme": ReadmeHelper,
#}
#
#_templates = {
#    "stdout": StdoutDefaultTemplate,
#    "readme": ReadmeDefaultTemplate,
#}
#
#class HelpTask(Task):
#    """display help page
#
#'help' task displays help page of a task on web browser.
#"""
#
#    _version_ = "0.1.0"
#    _name_ = "help"
#
#    def __init__(self, parent):
#
#        # TODO: doc template (default several templates)
#        # TODO: section template ( default many templates)
#        # TODO: pyloco provided information API
#
#        self.add_data_argument("task", required=None, type=Task, help="a task name")
#
#        self.add_option_argument("--format", default="stdout",
#                param_parse=True, help="help format (default=stdout)")
#        self.add_option_argument("--outdir", help="output directory")
##
##        self.add_option_argument("--user", help="generate user's manual")
##        self.add_option_argument("--developer", help="generate developer's manual")
##        self.add_option_argument("--readme", help="generate readme")
##
##        self.add_option_argument("-t", "--title", help="custom title")
##        self.add_option_argument("-l", "--oneliner", help="custom one-line description")
##        self.add_option_argument("-d", "--description", help="custom multi-line description")
##        self.add_option_argument("-u", "--usage", action="append", help="custom usage")
##        self.add_option_argument("-i", "--installation", help="custom installation direction")
##        self.add_option_argument("-s", "--section", action="append", help="custom section")
##        self.add_option_argument("-a", "--add", action="append", help="additional section")
##        self.add_option_argument("-n", "--headnote", help="headnote section")
##        self.add_option_argument("-e", "--footnote", help="footnote section")
##
##        self.add_option_argument(
##            "-o", "--output", default="pydoc",
##            help=("generate help for pyloco task in a specified format "
##                  "and file (valid options: 'pydoc', 'web', '.rst filepath',"
##                  " and '.htm[l] filepath'")
##        )
##        self.add_option_argument("-w", "--web", action="store_true",
##                                 help="display on web browser")
##
##    def run(self, argv, subargv=None, forward=None):
##
##        oidx = None
##
##        if "-o" in argv:
##            oidx = argv.index("-o")
##
##        if "--output" in argv:
##            oidx = argv.index("--output")
##
##        if oidx is not None:
##            if argv[oidx+1] == "web":
##                here = os.path.dirname(__file__)
##                argv.append("--webapp")
##                argv.append(os.path.join(here, "helptask"))
##                self.taskattr["webapp.wait2close"] = False
##
##        return super(HelpTask, self).run(argv, subargv, forward)
#
#    def perform(self, targs):
#
#        try:
#            if targs.task:
#                if issubclass(targs.task, Task):
#                    task_class = targs.task
#
#                else:
#                    task_class, argv, subargv, objs = load_taskclass(targs.task, [], [])
#
#            else:
#                from pyloco.task import OptionTask
#                task_class = OptionTask
#
#            task = task_class(self.get_proxy())
#            from pyloco.plxtask import PlXTask
#
#            if task_class is PlXTask:
#                task._setup(argv[0])
#            
#            helptype = targs.format.vargs[0]
#            helper = _helpers.get(helptype, StdoutHelper)
#
#            template = targs.format.kwargs.get("template", None)
#            if template is None:
#                template = _templates.get(helptype, StdoutDefaultTemplate)
#
#            elif os.path.isfile(template):
#                with open(template) as f:
#                    template = f.read()
#
#            else:
#                raise Exception("Help template is not found: %s" % template)
#
#            helper(task, targs)._generate(template)
#
#        except UsageError:
#
#            pydoc.Helper().help(targs.task)


class HelpTask(StandardTask):
    """display help page

'help' task displays help page of a task on web browser.
"""

    _version_ = "0.1.1"
    _name_ = "help"

    def __init__(self, parent):

        self.add_data_argument("task", required=None, help="a task name")

        self.add_option_argument("-d", "--define", nargs="*", param_parse=True, help="variable definition")
        self.add_option_argument("-f", "--format", default="readme", help="help format (default=readme)")
        self.add_option_argument("-t", "--template", help="template for output document")
        self.add_option_argument("-o", "--output", default="stdout", help="output destination")

    def perform(self, targs):

        if targs.task:
            try:
                task_class, argv, subargv, objs = load_taskclass(targs.task, [], [])

            except UsageError:
                pydoc.Helper().help(targs.task)
                return
        else:
            from pyloco.task import OptionTask
            task_class = OptionTask

        task = task_class(self.get_proxy())
        from pyloco.plxtask import PlXTask

        if task_class is PlXTask:
            task._setup(argv[0])

        if targs.template:
            with open(targs.template) as f:
                t = f.read()
        else:
            here = os.path.dirname(__file__)
            relpath = ("templates", "help", targs.format+"_t")
            tpath = os.path.join(here, *relpath)
            if os.path.isfile(tpath):
                with open(tpath) as f:
                    t = f.read()
            else:
                t = readme_template

        t1 = t.replace("{", "{{").replace("}", "}}")
        template = t1.replace("__{{", "{").replace("}}__", "}")

        # read docstring and other data
        short_desc = "[[short description is not available.]]"
        long_desc = "[[long description is not available.]]"
        sections = {}

        def _extract(n1, n2, lines):
            if isinstance(n1, section):
                n1 = n1.line
            elif n1.line is None:
                import pdb; pdb.set_trace()
            else:
                n1 = n1.line-1

            if n2 is None:
                n2 = len(lines)
            elif isinstance(n2, section):
                n2 = n2.line-3
            elif n2.line is None:
                import pdb; pdb.set_trace()
            else:
                n2 = n2.line-1
            return "\n".join(lines[n1:n2]).strip()

        if task.__doc__:
            lines = task.__doc__.splitlines()
            tree = publish_doctree(task.__doc__)

            secidx = [tree.children.index(n) for n in tree.children if isinstance(n, section)]

            # sections
            for psec, nsec in zip(secidx, secidx[1:]+[None]): 
                pnode = tree.children[psec]
                nnode = None if nsec is None else tree.children[nsec] 
                secbody = _extract(pnode, nnode, lines)

                for name in pnode["names"]:
                    sections[_lowerstrip(name)] = secbody

            sec0 = secidx[0] if secidx else len(tree.children)
            paras = [n for n in tree.children[:sec0] if isinstance(n, paragraph)]

            if paras:
                tail = tree.children[secidx[0]] if secidx else None
                paras += [tail]

                if tree.children.index(paras[0]) == 0:
                    pnode = paras[0]
                    nnode = paras[1]
                    short_desc = _extract(pnode, nnode, lines)

                    if len(paras) > 2:
                        pnode = paras[1]
                        nnode = paras[-1]
                        long_desc = _extract(pnode, nnode, lines)

                else:
                    pnode = paras[0]
                    nnode = paras[-1]
                    long_desc = _extract(pnode, nnode, lines)

        # replace items in template
        env = {}
        env["type"] = "task"

        for attr in dir(task_class):
            if (attr.startswith("_") and attr.endswith("_") and
                not attr.startswith("__") and not attr.endswith("__")):
                env[_lowerstrip(attr[1:-1])] = str(getattr(task_class, attr))

        prime = dict([(k,v) for k, v in env.items() if ("{" not in v and "}" not in v)])

        for key in env.keys():
            env[key] = env[key].format(**prime)


        env["shortdescription"] = short_desc
        env["longdescription"] = long_desc
        env.update(sections)

        if targs.define:
            for define in targs.define:
                for varg in vargs:
                    env[_lowerstrip(varg)] = varg

                for key, value in kwargs.items():
                    env[_lowerstrip(key)] = value

        fmt = PartialFormatter()
        output = fmt.format(template, **env)

        if targs.output == "stdout":
            print(output)

        else:
            with open(targs.output, "w") as f:
                f.write(output)


