# -*- coding: utf-8 -*-
"""web server module."""

from __future__ import unicode_literals

import sys
import os
import re
import shutil
import random
import tempfile

from collections import OrderedDict

here = os.path.abspath(os.path.dirname(__file__))

_pat_loadjs = r"\s*pyloco\s*\.\s*loadJavascript\s*\(\s*(?P<url>.+)\s*\)"
_re_loadjs = re.compile(_pat_loadjs)

_pat_cfg_header = re.compile(r"\[ *(?P<header>[^]]+?) *\]")


if sys.version_info >= (3, 0):
    from http.server import HTTPServer, BaseHTTPRequestHandler

else:
    from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler


def _e(s):

    return s.encode("utf-8")


html_noapp = """
<p>NO application is found.</p>
"""

html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />

<title>Pyloco Monitor V0.2</title>

<script language="javascript" type="text/javascript">

var pyloco = (function () {

    var websocket = null;
    var eventHandlers = {};
    var rawMsgs = [];
    var msgs = {};

    function getInfo(infotype, query) {

        result = null;

        if (infotype == "tasktype") {
            result = api[query];
        }

        return result;
    }

    function dynamicSort(property) {
        var sortOrder = 1;

        if(property[0] === "-") {
            sortOrder = -1;
            property = property.substr(1);
        }

        return function (a,b) {
            if(sortOrder == -1){
                return b[property].localeCompare(a[property]);
            }else{
                return a[property].localeCompare(b[property]);
            }
        }
    }

    function connect() {

        websocket = new WebSocket("ws://localhost:%(WEBSOCKET_PORT)d");

        websocket.onopen = function(evt) {
            websocket.send('browser')
            if ("open" in eventHandlers) { eventHandlers["open"](evt); }
        };

        websocket.onclose = function(evt) {
            if ("close" in eventHandlers) { eventHandlers["close"](evt); }
        };

        websocket.onmessage = function(evt) {

            window.console.log(evt);

            data = JSON.parse(evt.data);

            var msgId = rawMsgs.length
            rawMsg = {"id": msgId, "time": data["time"], "body": data["body"]};
            rawMsgs.push(rawMsg);

            var sender = data["sender"];

            if (sender in msgs) {
                var senderMsgs = msgs[sender];
                var msgType = data.type;
                if (msgType in senderMsgs) {
                    var typeMsgs = senderMsgs[msgType];
                    typeMsgs.data.push(msgId);
                    typeMsgs.callback(msgId, data.time, data.body);
                }
            }
        };

        websocket.onerror = function(evt) {
            websocket.close();
            if ("error" in eventHandlers) { eventHandlers["error"](evt); }
        };
    }

    window.addEventListener("load", connect, false);

    function setOpenEventHandler (func) {
        eventHandlers["open"] = func;
    }

    function setCloseEventHandler (func) {
        eventHandlers["close"] = func;
    }

    function setErrorEventHandler (func) {
        eventHandlers["error"] = func;
    }

    function setMessageEventHandler (sender, msgType, func) {

        if (sender in msgs) {
            var senderMsgs = msgs[sender];
        } else {
            var senderMsgs = {};
            msgs[sender] = senderMsgs;
        }

        if (msgType in senderMsgs) {
            senderMsgs[msgType]["callback"] = func;
        } else {
            var typeMsgs = {"callback": func, data: []};
            senderMsgs[msgType] = typeMsgs;
        }
    }

    function sendMessage (msgType, msg) {
        websocket.send({"time": Date.now(), "sender": "browser",
            "type": msgType, "body": msg});
    }

    function disconnectWebsocket () {
        websocket.close()
    };

    function checkJavascriptLoaded (js) {
        // TODO: implement this
    };

    var api = {
        onOpen          : setOpenEventHandler,
        onClose         : setCloseEventHandler,
        onError         : setErrorEventHandler,
        onMessage       : setMessageEventHandler,
        send            : sendMessage,
        disconnect      : disconnectWebsocket,
        loadJavascript  : checkJavascriptLoaded,
        getInfo         : getInfo,

        Manager         : 0,
        Task            : 1,
        PylocoTask      : 2,
        GroupTask       : 3,
        PyXScriptTask   : 4,
        ScriptTask      : 5,
        Section         : 6,
        MultitaskTask   : 7,
    }

    return api;

})();
</script>

%(JAVASCRIPTS)s

%(CSS)s

</head>
<body>
</body>
<script type="text/javascript" src="%(WEBAPP)s.js"></script>
</html>
"""


def _extract_external_javascripts(jspath, docroot):

    extjs = []

    with open(jspath) as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            match = _re_loadjs.match(line)

            if match:
                extjs.append(match.group("url"))
                continue

            break

    scripts = []
    jsdir = os.path.dirname(jspath)

    for js in extjs:
        extjspath = eval(js)

        if os.path.exists(extjspath):
            shutil.copy(extjspath, docroot)

        elif os.path.exists(os.path.join(jsdir, extjspath)):
            shutil.copy(os.path.join(jsdir, extjspath), docroot)

        scripts.append('<script src=%s type="text/javascript"></script>' % js)

    return "\n".join(scripts)


class PylocoWebServer(HTTPServer):

    def serve_forever(self):

        self.stop = False

        while not self.stop:
            self.handle_request()

    def add_app(self, name, code, externals, css=False):

        self.webapps[name] = (code, css, externals)


class WebRequestHandler(BaseHTTPRequestHandler):

    def _send_header(self):
        self.send_response(200)
        self.send_header(_e("Content-type"), _e("text/html"))
        self.end_headers()

    def do_HEAD(self):

        self._send_header()

    def do_GET(self):

        try:

            sendReply = False

            if self.path.endswith("/"):
                self.path = self.path[:-1]

            appname = None

            if self.path:
                basename = os.path.basename(self.path)
                if basename in self.server.webapps:
                    appname = basename
            elif self.server.webapps:
                appname = list(self.server.webapps.keys())[0]

            if appname is not None:
                self._send_header()
                code, css, javascripts = self.server.webapps[appname]
                sk_port = self.server.websocket_port

                if css:
                    csstag = ('<link rel="stylesheet" type="text/css" '
                              'href="%s.css">' % code)
                else:
                    csstag = ""

                self.wfile.write(
                    _e(html % {"WEBSOCKET_PORT": sk_port, "WEBAPP": code,
                               "CSS": csstag, "JAVASCRIPTS": javascripts})
                )

            elif self.path.endswith(".js"):
                mimetype = 'application/javascript'
                sendReply = True

            elif self.path.endswith(".css"):
                    mimetype = 'text/css'
                    sendReply = True

            elif self.path.endswith(".ico"):
                    mimetype = 'image/x-icon'
                    sendReply = True

            elif sendReply is not True:
                self.send_error(404, 'File Not Found: %s' % self.path)

            if sendReply is True:
                    # Open the static file requested and send it
                    with open(self.server.docroot + self.path) as f:
                        self.send_response(200)
                        self.send_header(_e('Content-type'), mimetype)
                        self.end_headers()
                        self.wfile.write(_e(f.read()))
        except IOError:
            self.send_error(404, 'File Not Found: %s' % self.path)

    def do_POST(self):
        self._send_header()
#
#        if self.path=="/send":
#                    form = cgi.FieldStorage(
#                            fp=self.rfile,
#                            headers=self.headers,
#                            environ={'REQUEST_METHOD':'POST',
#                             'CONTENT_TYPE':self.headers['Content-Type'],
#                    })
#
#            print "Your name is: %s" % form["your_name"].value
#            self.send_response(200)
#            self.end_headers()
#            self.wfile.write("Thanks %s !" % form["your_name"].value)
#            return

    def do_QUIT(self):

        print("Exiting http server...")
        self._send_header()
        self.server.stop = True

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":

    import multiprocessing
    multiprocessing.freeze_support()

    try:

        tempdir = tempfile.mkdtemp()

        server = PylocoWebServer(("localhost", int(sys.argv[1])),
                                 WebRequestHandler)
        # server = PylocoWebServer(("::", int(sys.argv[1])), WebRequestHandler)

        server.websocket_port = int(sys.argv[2])
        server.docroot = tempdir
        server.webapps = OrderedDict()

        for path in sys.argv[3:]:
            name = os.path.basename(path)
            code = "a%d" % random.randint(1E8, 1E9)
            js = path + ".js"
            if os.path.isfile(js):
                externals = _extract_external_javascripts(js, tempdir)
                shutil.copy(js, os.path.join(tempdir, code + ".js"))
                css = path + ".css"
                if os.path.isfile(css):
                    shutil.copy(css, os.path.join(tempdir, code + ".css"))
                    server.add_app(name, code, externals, css=True)
                else:
                    server.add_app(name, code, externals)
            else:
                print("WARNING: could not find webapp '%s'." % path)

        server.serve_forever()

    except KeyboardInterrupt:

        server.socket.close()

    finally:

        shutil.rmtree(tempdir)
