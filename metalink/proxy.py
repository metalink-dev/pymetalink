#!/usr/bin/env python
########################################################################
#
# Project: pyMetalink
# URL: https://github.com/metalink-dev/pymetalink
# E-mail: nabber00@gmail.com
#
# Copyright: (C) 2007-2016 Neil McNab and Hampus Wessman
# License: MIT
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# Description:
#   Library to make proxied Python connections easy.
#
# Library Instructions:
#   - Use as described with standard urllib2 calls.  You can also use the
# following objects as replacements for the builtins:
#
#   ftplib.FTP => proxy.FTP
#   httplib.HTTPConnection => proxy.HTTPConnection
#   httplib.HTTPSConnection => proxy.HTTPSConnection
#
# import metalink.proxy
#
# # optional, set your own proxy settings
# metalink.proxy.HTTP_PROXY = "http://user:pass@myproxy:80"
#
# # initialize proxy from whatever system settings we can find
# metalink.proxy.set_proxies()
#
# # all urllib2 calls are now configured for proxy
# urllib2.urlopen("http://example.com/test.html")
#
########################################################################

import base64
import ftplib
import gettext
import http.client
import locale
import os
import platform
import sys
import urllib
import urllib.parse
import urllib.request
import winreg

unicode = str
# Configure proxies (user and password optional)
# HTTP_PROXY = http://user:password@myproxy:port
HTTP_PROXY = ""
FTP_PROXY = ""
HTTPS_PROXY = ""
SOCKS_PROXY = ""


def translate():
    """
    Setup translation path
    """
    if __name__ == "__main__":
        base = ""
        localedir = ""
        try:
            base = os.path.basename(__file__)[:-3]
            localedir = os.path.join(os.path.dirname(__file__), "locale")
        except NameError:
            if sys.executable is not None:
                base = os.path.basename(sys.executable)[:-4]
                localedir = os.path.join(os.path.dirname(sys.executable), "locale")
    else:
        temp = __name__.split(".")
        base = temp[-1]
        localedir = os.path.join("/".join(["%s" % k for k in temp[:-1]]), "locale")

    # print base, localedir
    locale_lang = locale.getdefaultlocale()[0]
    if locale_lang is None:
        locale_lang = "LC_ALL"
    t = gettext.translation(base, localedir, [locale_lang], None, "en")
    return t.gettext

_ = translate()


def get_key_value(key, value):
    """
    Probes registry
    First parameter, key to look in
    Second parameter, value name to extract
    Returns the value as a string
    """
    # does not handle non-paths yet
    result = ""

    try:
        with winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER) as registry:
            with winreg.OpenKey(registry, key) as registry_key:
                value_ex = winreg.QueryValueEx(registry_key, value)
                result = str(value_ex[0])
    except:
        pass

    result = unicode(os.path.expandvars(result))
    return result


def get_proxy_info():
    global HTTP_PROXY
    global FTP_PROXY
    global HTTPS_PROXY
    global SOCKS_PROXY

    HTTP_PROXY = ""
    FTP_PROXY = ""
    HTTPS_PROXY = ""
    SOCKS_PROXY = ""

    # from environment variables
    if "http_proxy" in os.environ and HTTP_PROXY == "":
        HTTP_PROXY = os.environ["http_proxy"]
    if "ftp_proxy" in os.environ and FTP_PROXY == "":
        FTP_PROXY = os.environ["ftp_proxy"]
    if "https_proxy" in os.environ and HTTPS_PROXY == "":
        HTTPS_PROXY = os.environ["https_proxy"]

    if platform.system() == 'Windows':
        # from IE in registry
        proxy_enable = get_key_value(
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            "ProxyEnable"
        )
        try:
            proxy_enable = bool(proxy_enable[-1])
        except IndexError:
            proxy_enable = False

        if proxy_enable:
            proxy_string = get_key_value(
                "Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings",
                "ProxyServer",
            )
            if not "=" in proxy_string:
                # if all use the same settings
                for proxy in ("HTTP_PROXY", "FTP_PROXY", "HTTPS_PROXY"):
                    if getattr(sys.modules[__name__], proxy) == "":
                        setattr(sys.modules[__name__], proxy, "http://" + str(proxy_string))
            else:
                proxies = proxy_string.split(";")
                for proxy in proxies:
                    name, value = proxy.split("=")
                    if getattr(sys.modules[__name__], name.upper() + "_PROXY") == "":
                        setattr(sys.modules[__name__], name.upper() + "_PROXY", "http://" + value)
    else:
        # Todo
        pass


get_proxy_info()


class ftpwrapper(urllib.request.ftpwrapper):
    """Class used by open_ftp() for cache of open FTP connections."""

    def init(self):
        self.busy = 0
        self.ftp = FTP()
        self.ftp.connect(self.host, self.port, self.timeout)
        self.ftp.login(self.user, self.passwd)
        self.dir = "/" + "/".join(self.dirs) + "/"

    def retrfile(self, file, type):
        self.endtransfer()
        if type in ("d", "D"):
            cmd = "TYPE A"
            isdir = 1
        else:
            cmd = "TYPE " + type
            isdir = 0
        try:
            self.ftp.voidcmd(cmd)
        except ftplib.all_errors:
            self.init()
            # TODO catch this error
            # try:
            self.ftp.voidcmd(cmd)
            # except: pass
        conn = None
        if file and not isdir:
            # Try to retrieve as a file
            try:
                cmd = "RETR " + self.dir + file
                conn = self.ftp.ntransfercmd(cmd)
            except ftplib.error_perm as reason:
                if str(reason)[:3] != "550":
                    raise OSError(("ftp error", reason), sys.exc_info()[2])

        self.busy = 1
        # Pass back both a suitably decorated object and a retrieval length
        return urllib.addclosehook(conn[0].makefile("rb"), self.endtransfer), conn[1]

    def endtransfer(self):
        if not self.busy:
            return
        self.busy = 0
        try:
            self.ftp.voidresp()
        # FIXME: There is no such exception as ftperrors
        except ftperrors():
            pass

    def close(self):
        self.endtransfer()
        try:
            self.ftp.close()
        # FIXME: There is no such exception as ftperrors
        except ftperrors():
            pass


def set_proxies():
    # Set proxies
    proxies = getproxies()

    proxy_handler = urllib.request.ProxyHandler(proxies)
    opener = urllib.request.build_opener(proxy_handler)

    # install this opener
    urllib.request.install_opener(opener)


def getproxies():
    proxies = {}

    if HTTP_PROXY != "":
        proxies["http"] = HTTP_PROXY
    if HTTPS_PROXY != "":
        proxies["https"] = HTTPS_PROXY
    if FTP_PROXY != "":
        proxies["ftp"] = FTP_PROXY

    return proxies


########### PROXYING OBJECTS ########################


class FancyURLopener(urllib.request.FancyURLopener):
    def open(self, fullurl, data=None):
        return urllib.request.urlopen(fullurl, data)


class FTP(ftplib.FTP):
    def __init__(self, *args, **kwargs):
        self.headers = {}
        ftplib.FTP.__init__(self, *args, **kwargs)

    def connect(self, host="", port=0, timeout=-999):
        if FTP_PROXY != "":
            if port == 0:
                port = ftplib.FTP_PORT
            # parse proxy URL
            url = urllib.parse.urlparse(FTP_PROXY)
            if not (url[0] == "" or url[0] == "http"):
                raise AssertionError(
                    _("Transport not supported for FTP_PROXY, %s") % url.scheme
                )

            port = http.client.HTTP_PORT
            if url[1].find("@") != -1:
                host = url[1].split("@", 2)[1]
            else:
                host = url[1]

            if url.port is not None:
                port = url.port
            if url.username is not None:
                self.headers["Proxy-authorization"] = (
                    "Basic "
                    + base64.encodestring(url.username + ":" + url.password)
                    + "\r\n"
                )

            self.conn = http.client.HTTPConnection(host, port)
            return None

        else:
            return ftplib.FTP.connect(self, host, port, timeout)

    def login(self, *args, **kwargs):
        if FTP_PROXY == "":
            return ftplib.FTP.login(self, *args, **kwargs)

    def ntransfercmd(self, cmd, rest=0, rest_end=None):
        if FTP_PROXY != "":
            if cmd.startswith("RETR"):
                url = cmd.split(" ", 2)

                headers = {}
                headers.update(self.headers)
                if not (rest == 0 and rest_end is None):
                    if rest_end is None:
                        rest_end = self.size(url)
                    headers["Range"] = "bytes=%lu-%lu\r\n" % (rest, rest_end)

                result = self.conn.request("GET", url, "", headers)
                result.recv = result.read
                # FIXME: There is no size variable in the result object
                return result, size
            return None, None
        else:
            return ftplib.FTP.ntransfercmd(self, cmd, rest)

    def getmultiline(self):
        if FTP_PROXY == "":
            return ftplib.FTP.getmultiline(self)
        return "500: Not available through HTTP proxy."

    def size(self, filename):
        if FTP_PROXY != "":
            # print "HEAD", filename
            result = self.conn.request("HEAD", filename)
            return int(result.getheader("Content-length", None))
        else:
            return ftplib.FTP.size(self, filename)

    def exist(self, url):
        if FTP_PROXY != "":
            result = self.conn.request("HEAD", url)
            if result.status < 400:
                return True
            return False
        else:
            url_parts = urllib.parse.urlsplit(url)
            try:
                files = ftplib.FTP.nlst(self, os.path.dirname(url_parts.path))
            except:
                return False

            # directory listing can be in two formats, full path or current directory
            if (os.path.basename(url_parts.path) in files) or (url_parts.path in files):
                return True

            return False

    def quit(self):
        if FTP_PROXY != "":
            return self.close()
        else:
            return ftplib.FTP.quit(self)

    def close(self):
        if FTP_PROXY != "":
            self.conn.close()
        else:
            ftplib.FTP.close(self)



class HTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, port=None, *args, **kwargs):
        super().__init__(host, port, *args, **kwargs)

        if HTTP_PROXY:
            headers = {}
            proxy = urllib.parse.urlparse(HTTP_PROXY)
            if proxy.scheme not in ("", "http"):
                raise ValueError(f"Transport {proxy.scheme} not supported for HTTP_PROXY")

            if proxy.username:
                # Encode username and password for proxy authorization
                userpass = f"{proxy.username}:{proxy.password}"
                encoded_userpass = base64.b64encode(userpass.encode()).decode()
                headers["Proxy-Authorization"] = f"Basic {encoded_userpass}"

            # Set up the tunnel through the proxy
            self.set_tunnel(host, port, headers)

            # Update host and port to the proxy
            self.host = proxy.hostname
            self.port = proxy.port if proxy.port else http.client.HTTP_PORT


class HTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, port=None, *args, **kwargs):
        super().__init__(host, port, *args, **kwargs)

        if HTTPS_PROXY:
            headers = {}
            proxy = urllib.parse.urlparse(HTTPS_PROXY)
            if proxy.scheme not in ("", "http"):
                raise ValueError(f"Transport {proxy.scheme} not supported for HTTPS_PROXY")

            if proxy.username:
                # Encode username and password for proxy authorization
                userpass = f"{proxy.username}:{proxy.password}"
                encoded_userpass = base64.b64encode(userpass.encode()).decode()
                headers["Proxy-Authorization"] = f"Basic {encoded_userpass}"

            # Set up the tunnel through the proxy
            self.set_tunnel(host, port, headers)

            # Update host and port to the proxy
            self.host = proxy.hostname
            self.port = proxy.port if proxy.port else http.client.HTTP_PORT


# def test_urllib2(url):
# handle = urllib2.urlopen(url)
# #print handle.read()
# print len(handle.read())
# handle.close()

# def test_urllib(url):
# replace()
# handle = urllib.urlopen(url)
# #print handle.read()
# print len(handle.read())
# handle.close()

# if __name__=="__main__":
# set_proxies()
# print HTTP_PROXY, HTTPS_PROXY, FTP_PROXY

# # TODO FTP
# #test_urllib2("https://www.nabber.org")
# #test_urllib2("ftp://ftp.freebsd.org/pub/FreeBSD/README.TXT")
# #HTTP_PROXY = "http://gatekeeper-w:80"
# #HTTPS_PROXY = "http://gatekeeper-w:80"
# FTP_PROXY = "http://127.0.0.1:8000"
# HTTP_PROXY = "http://127.0.0.1:8000"
# HTTPS_PROXY = "http://127.0.0.1:8000"
# print HTTP_PROXY, HTTPS_PROXY, FTP_PROXY
# set_proxies()
# print get_proxies()
# test_urllib2("ftp://ftp.freebsd.org/pub/FreeBSD/README.TXT")
# test_urllib("http://www.google.com")
# test_urllib("https://encrypted.google.com")

# print "opening"
##    c = HTTPSConnection("encrypted.google.com")
##    print "connect"
##    #c.connect()
##    print "send GET"
##    c.request("GET", "https://encrypted.google.com/")
##    print "response"
##    print len(c.getresponse().read())
##    print "closing"
##    c.close()
##    print "closed"

#    HTTP_PROXY = "user:password@localhost:8000"
#    HTTPS_PROXY = "user:password@localhost:8000"
#    set_proxies()
