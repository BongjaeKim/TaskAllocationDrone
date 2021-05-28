# -*- coding: utf-8 -*-

"""Pyloco websocket app."""

from __future__ import unicode_literals

import sys
import time

from pyloco.util import PY3

from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket

if PY3:
    from http.client import HTTPConnection

else:
    from httplib import HTTPConnection


class PylocoWebSocketServer(SimpleWebSocketServer):

    def serveforever(self):

        self.stop = False

        while not self.stop:
            self.serveonce()


class SocketHandler(WebSocket):

    clients = {}

    def __init__(self, server, sock, address):

        super(SocketHandler, self).__init__(server, sock, address)
        self.client_type = None

    def error(self):
        pass

    def handleMessage(self):

        if self.client_type is None:
            if self.data in ("browser", "pyloco"):
                self.client_type = self.data
                self.clients[self.data] = self
        else:
            getattr(self, self.client_type+"_message", self.error)()

    def handleConnected(self):

        if self.client_type is not None:
            getattr(self, self.client_type+"_connected", self.error)()

    def handleClose(self):

        if self.client_type is not None:
            getattr(self, self.client_type+"_close", self.error)()

    ###############################
    # browser
    ###############################
    def browser_message(self):

        self.sendMessage("Hi, %d!" % self.server.webserver_port)

    def browser_connected(self):
        pass

    def browser_close(self):

        print("Exiting websocket server...")
        conn = HTTPConnection("localhost:%d" % self.server.webserver_port)
        conn.request("QUIT", "/")
        conn.getresponse()
        self.server.stop = True

    ###############################
    # pyloco
    ###############################
    def pyloco_message(self):

        if self.data == "check_browser":
            self.sendMessage(str("browser" in self.clients))

        else:
            self.sendMessage("OK")

            if "browser" in self.clients:
                self.clients["browser"].sendMessage(self.data)

    def pyloco_connected(self):

        pass
        #if "browser" in self.clients:
        #    self.clients["browser"].sendMessage("pyloco is connected.")

    def pyloco_close(self):

        pass
        #if "browser" in self.clients:
        #    self.clients["browser"].sendMessage("pyloco is closed.")


if __name__ == "__main__":

    import multiprocessing
    multiprocessing.freeze_support()

    try:
        server = PylocoWebSocketServer("localhost", int(sys.argv[1]),
                                       SocketHandler)
        server.webserver_port = int(sys.argv[2])
        server.serveforever()

    except KeyboardInterrupt:
        server.socket.close()
