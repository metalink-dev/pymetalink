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
#   Download library that can handle metalink files, RFC 5854, RFC 6249.
# Also supports Instance Digests, RFC 3230.
#
# Library Instructions:
#   - Use as expected.
#
# import metalink.download
#
# files = metalink.download.get("file.metalink", os.getcwd())
# fp = metalink.download.urlopen("file.metalink")
#
# Callback Definitions:
# def cancel():
#   Returns True to cancel, False otherwise
# def pause():
#   Returns True to pause, False to continue/resume
# def status(block_count, block_size, total_size):
#   Same format as urllib.urlretrieve reporthook
#   block_count - a count of blocks transferred so far
#   block_size - a block size in bytes
#   total_size - the total size of the file in bytes
# def bitrate(bitrate):
#   bitrate - kilobits per second (float)
#
########################################################################
import base64
import binascii
import copy
import ftplib
import gettext
import hashlib
import http.client
import http.server
import io
import locale
import os
import random
import socket
import ssl
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from typing import List, Callable

import metalink

try:
    import GPG
except ImportError:
    try:
        from . import GPG
    except:
        pass

# for new python3 package handling
try:
    import proxy
except ImportError:
    from . import proxy

# for jython support
# try: import bz2
# except ImportError: pass

# Deprecated since Python version 3.6
# OpenSSL has deprecated all version specific protocols.
SSL_ANYTHING = ssl.SSLContext(ssl.PROTOCOL_TLS)  # previously, ssl.PROTOCOL_SSLv23
SSL_DEFAULT = ssl.create_default_context()
SSL_HIGH = ssl.SSLContext(ssl.PROTOCOL_TLS)  # previously, ssl.PROTOCOL_TLSv1_2
SSL_HIGH.verify_mode = ssl.CERT_REQUIRED
SSL_HIGH.verify_flags = ssl.VERIFY_CRL_CHECK_CHAIN
SSL_HIGH.set_ciphers(
    "ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES256-GCM-SHA384:DHE-RSA-AES128-GCM-SHA256:DHE-DSS-AES128-GCM-SHA256:kEDH+AESGCM:ECDHE-RSA-AES128-SHA256:ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA:ECDHE-ECDSA-AES128-SHA:ECDHE-RSA-AES256-SHA384:ECDHE-ECDSA-AES256-SHA384:ECDHE-RSA-AES256-SHA:ECDHE-ECDSA-AES256-SHA:DHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA:DHE-DSS-AES128-SHA256:DHE-RSA-AES256-SHA256:DHE-DSS-AES256-SHA:DHE-RSA-AES256-SHA:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!3DES:!MD5:!PSK"
)

USER_AGENT = "pyMetalink/6.1 +https://github.com/metalink-dev/pymetalink/"
UUID = None

SEGMENTED = True
LIMIT_PER_HOST = 1
HOST_LIMIT = 5
MAX_REDIRECTS = 20
CONNECT_RETRY_COUNT = 3

MAX_CHUNKS = 256
DEFAULT_CHUNK_SIZE = 262144

LANG = []
OS = None
COUNTRY = None

lang = locale.getdefaultlocale()[0]
if lang is None:
    lang = "LC_ALL"
lang = lang.replace("_", "-").lower()
LANG = [lang]

if len(lang) == 5:
    COUNTRY = lang[-2:]

PGP_KEY_DIR = "."
PGP_KEY_EXTS = (".gpg", ".asc")
PGP_KEY_STORE = None

# Streaming server settings to use
HOST = "localhost"
PORT = None

# Protocols to use for segmented downloads
PROTOCOLS = ("http", "https", "ftp")
# PROTOCOLS=("ftp")

# See http://www.poeml.de/transmetalink-test/README
MIME_TYPE = "application/metalink+xml"

DIGESTS = "md5,sha,sha-256,sha-384,sha-512"


def translate() -> Callable[[str], str]:
    """Setup translation path."""
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

    locale_lang = locale.getdefaultlocale()[0]
    if locale_lang is None:
        locale_lang = "en"  # Fallback to "en" if no system locale is found

    try:
        # Load translation
        t = gettext.translation(
            domain=base, localedir=localedir, languages=[locale_lang], fallback=True
        )
    except FileNotFoundError:
        # If the translation file doesn't exist, use a fallback
        t = gettext.NullTranslations()

    return t.gettext


_ = translate()


def set_uuid(uuidval=None):
    """Set uuid to None to clear, returns true on set success"""
    global UUID

    if uuidval is None:
        UUID = None
        return True
    # check uuid format
    try:
        parseduuid = uuid.UUID(uuidval)
    except ValueError:
        return False
    UUID = str(parseduuid)
    return True


def get_uuid():
    """if not set return None"""
    return UUID


def urlopen(url, data=None, metalink_header=False, headers={}):
    # print "URLOPEN:", url, headers
    url = complete_url(url)
    req = urllib.request.Request(url, data, headers)
    req.add_header("User-agent", USER_AGENT)
    if UUID:
        req.add_header(
            "Authorization", "Basic " + base64.encodestring("%s:" % UUID).strip()
        )
    req.add_header("Cache-Control", "no-cache")
    req.add_header("Pragma", "no-cache")
    req.add_header("Accept-Encoding", "gzip")
    req.add_header("Want-Digest", DIGESTS)
    if metalink_header:
        req.add_header("Accept", MIME_TYPE + ", */*")

    fp = urllib.request.urlopen(req)
    try:
        if fp.headers["Content-Encoding"] == "gzip":
            return metalink.open_compressed(fp)
    except KeyError:
        pass

    return fp


def urlhead(url, metalink_header=False, headers={}):
    """
    raise IOError for example if the URL does not exist
    """
    # print "URLHEAD:", url, headers
    url = complete_url(url)
    req = urllib.request.Request(url, None, headers)
    req.add_header("User-agent", USER_AGENT)
    if UUID:
        req.add_header(
            "Authorization", "Basic " + base64.encodestring("%s:" % UUID).strip()
        )
    req.add_header("Cache-Control", "no-cache")
    req.add_header("Pragma", "no-cache")
    req.add_header("Want-Digest", DIGESTS)
    if metalink_header:
        req.add_header("Accept", MIME_TYPE + ", */*")

    req.get_method = lambda: "HEAD"
    # logging.debug(url)
    fp = urllib.request.urlopen(req)
    new_headers = fp.headers
    fp.close()
    return new_headers


def digest_parse(digest):
    if digest is None:
        return {}

    hashes = digest.split(",")
    digest_sums = {}
    for hash_str in hashes:
        parts = hash_str.split("=", 1)
        # create digest list here
        if parts[0].strip() == "sha":
            digest_sums["sha-1"] = binascii.hexlify(
                binascii.a2b_base64(parts[1].strip())
            )
        else:
            digest_sums[parts[0].strip()] = binascii.hexlify(
                binascii.a2b_base64(parts[1].strip())
            )
    return digest_sums


def get(
    src,
    path,
    checksums=None,
    force=False,
    handlers=None,
    segmented=SEGMENTED,
    headers=None,
):
    """
    Download a file, decodes metalinks.
    First parameter, file to download, URL or file path to download from
    Second parameter, file path to save to
    Third parameter, optional, expected dictionary of checksums
    Fourth parameter, optional, force a new download even if a valid copy already exists
    Fifth parameter, optional, progress handler callback
    Sixth parameter, optional, boolean to try using segmented downloads
    Returns list of file paths if download(s) is successful
    Returns False otherwise (checksum fails)
    raise socket.error e.g. "Operation timed out"
    """
    if checksums is None:
        checksums = {}
    if handlers is None:
        handlers = {}
    if headers is None:
        headers = {}

    if src.endswith(".jigdo"):
        return download_jigdo(src, path, force, handlers, segmented, headers)
    # assume metalink if ends with .metalink

    result = download_metalink(src, path, force, handlers, segmented, headers)
    if result is not None:
        return result

    # assume normal file download here
    # parse out filename portion here
    filename = os.path.basename(src)
    result = download_file(
        src,
        os.path.join(path, filename),
        0,
        checksums,
        force,
        handlers,
        segmented=segmented,
        headers=headers,
    )
    if result:
        return [result]
    return False


def download_file(
    url,
    local_file,
    size=0,
    checksums=None,
    force=False,
    handlers=None,
    segmented=SEGMENTED,
    chunksums=None,
    chunk_size=0,
    headers=None,
):
    """
    url {string->URL} locations of the file
    local_file string local file name to save to
    checksums ?
    force ?
    handler ?
    segmented ?
    chunksums ?
    chunk_size ?
    returns unicode Returns file path if download is successful.
        Returns False otherwise (checksum fails).
    """
    if checksums is None:
        checksums = {}
    if handlers is None:
        handlers = {}
    if chunksums is None:
        chunksums = {}
    if headers is None:
        headers = {}

    file_obj = metalink.MetalinkFile(local_file)
    # Need to set this again for absolute file paths
    file_obj.filename = local_file
    file_obj.set_size(size)
    file_obj.hashlist = checksums
    file_obj.pieces = chunksums
    file_obj.piecelength = chunk_size
    file_obj.add_url(url)

    return download_file_urls(file_obj, force, handlers, segmented, headers)


def download_file_urls(
    metalinkfile, force=False, handlers=None, segmented=SEGMENTED, headers=None
):
    """
    Download a file.
    MetalinkFile object to download
    Second parameter, optional, force a new download even if a valid copy already exists
    Third parameter, optional, progress handler callback
    Fourth parameter, optional, try to use segmented downloading
    Returns file path if download is successful
    Returns False otherwise (checksum fails)
    """
    if handlers is None:
        handlers = {}
    if headers is None:
        headers = {}

    if os.path.exists(metalinkfile.filename) and (not force):
        act_size = os.stat(metalinkfile.filename).st_size
        if len(metalinkfile.hashlist) > 0:
            checksum = verify_checksum(metalinkfile.filename, metalinkfile.hashlist)
            if checksum:
                handlers["status"](1, act_size, act_size)
                print("")
                print(
                    _("Already downloaded %s.")
                    % os.path.basename(metalinkfile.filename)
                )
                return metalinkfile.filename
            else:
                print(
                    _("Checksum failed, retrying download of %s.")
                    % os.path.basename(metalinkfile.filename)
                )

        if metalinkfile.size == act_size:
            if "status" in handlers:
                handlers["status"](1, act_size, act_size)
            print("")
            print(_("Already downloaded %s.") % os.path.basename(metalinkfile.filename))
            return metalinkfile.filename

        if os.path.exists(metalinkfile.filename + ".temp"):
            print(
                _("Resuming download of %s.") % os.path.basename(metalinkfile.filename)
            )

    directory = os.path.dirname(metalinkfile.filename)
    if not os.path.isdir(directory):
        os.makedirs(directory)

    if metalinkfile.piecelength == 0:
        metalinkfile.piecelength = DEFAULT_CHUNK_SIZE

    print(_("Downloading to %s.") % metalinkfile.filename)

    seg_result = False
    if segmented:
        manager = Segment_Manager(metalinkfile, headers)
        manager.set_callbacks(handlers)
        seg_result = manager.run()

        if not seg_result:
            # seg_result = verify_checksum(local_file, checksums)
            print(
                "\n"
                + _(
                    "Could not download all segments of the file, trying one mirror at a time."
                )
            )

    if (not segmented) or (not seg_result):
        manager = NormalManager(metalinkfile, headers)
        manager.set_callbacks(handlers)
        manager.run()

    if manager is not None:
        if manager.get_status():
            return metalinkfile.filename
    return False


class Manager:
    def __init__(self):
        self.cancel_handler = None
        self.pause_handler = None
        self.status_handler = None
        self.bitrate_handler = None
        self.time_handler = None
        self.status = True
        self.size = -1
        self.end_bitrate()

    def set_time_callback(self, handler):
        self.time_handler = handler

    def set_cancel_callback(self, handler):
        self.cancel_handler = handler

    def set_pause_callback(self, handler):
        self.pause_handler = handler

    def set_status_callback(self, handler):
        self.status_handler = handler

    def set_bitrate_callback(self, handler):
        self.bitrate_handler = handler

    def set_callbacks(self, callbackdict):
        for key in callbackdict.keys():
            setattr(self, key + "_handler", callbackdict[key])

    def run(self, wait=None):
        """
        Return True on success, false on error
        """
        result = self.status
        while result:
            if self.pause_handler is not None and self.pause_handler():
                self.end_bitrate()
                time.sleep(1)
            else:
                if wait is not None:
                    time.sleep(wait)
                result = self.cycle()

        return self.get_status()

    def cycle(self):
        """
        return True to continue in loop, false to exit
        """
        pass

    def get_status(self):
        return self.status

    def close_handler(self):
        return

    def start_bitrate(self, bytes):
        """
        Pass in current byte count
        """
        self.oldsize = bytes
        self.oldtime = time.time()

    def end_bitrate(self):
        self.oldsize = 0
        self.oldtime = None

    def get_bitrate(self, bytes):
        """
        Pass in current byte count
        """
        if self.oldtime is not None and (time.time() - self.oldtime) != 0:
            return ((bytes - self.oldsize) * 8 / 1024) / (time.time() - self.oldtime)
        return 0

    def get_time(self, bytes):
        bitrate = self.get_bitrate(bytes)
        if bitrate == 0 or (self.size - bytes) < 0:
            return "??:??"

        seconds_left = (self.size - bytes) / (bitrate * 1024 / 8)
        hours = seconds_left / 3600
        minutes = (seconds_left % 3600) / 60
        seconds = seconds_left % 60
        if int(hours) > 0:
            return "%.2d:%.2d:%.2d" % (hours, minutes, seconds)
        return "%.2d:%.2d" % (minutes, seconds)


class NormalManager(Manager):
    def __init__(self, metalinkfile, headers={}):
        Manager.__init__(self)
        self.local_file = metalinkfile.filename
        self.size = metalinkfile.size
        self.chunksums = metalinkfile.get_piece_dict()
        self.checksums = metalinkfile.hashlist
        self.urllist = start_sort(metalinkfile.get_url_dict())
        self.start_number = 0
        self.number = 0
        self.count = 0
        self.headers = headers.copy()

    def random_start(self):
        # do it the old way
        # choose a random url tag to start with
        # urllist = list(urllist)
        # number = int(random.random() * len(urllist))
        self.start_number = int(random.random() * len(self.urllist))
        self.number = self.start_number

    def cycle(self):
        if self.cancel_handler is not None and self.cancel_handler():
            return False
        try:
            self.status = True
            remote_file = complete_url(self.urllist[self.number])

            manager = URLManager(
                remote_file, self.local_file, self.checksums, self.headers
            )
            manager.set_status_callback(self.status_handler)
            manager.set_cancel_callback(self.cancel_handler)
            manager.set_pause_callback(self.pause_handler)
            manager.set_bitrate_callback(self.bitrate_handler)
            manager.set_time_callback(self.time_handler)
            self.get_bitrate = manager.get_bitrate
            manager.run()
            # print self.status
            if manager.get_status():
                return False

            self.number = (self.number + 1) % len(self.urllist)
            self.count += 1

            if self.count == len(self.urllist):
                self.status = False

            return self.count < len(self.urllist)
        except KeyboardInterrupt:
            print("Download Interrupted!")
            try:
                manager.close_handler()
            except:
                pass
            return False


class URLManager(Manager):
    def __init__(self, remote_file, filename, checksums={}, headers={}):
        """
        modernized replacement for urllib.urlretrieve() for use with proxy
        """
        Manager.__init__(self)
        self.filename = filename
        self.checksums = checksums
        self.block_size = 1024
        self.counter = 0
        self.total = 0

        ### FIXME need to check contents from previous download here
        self.resume = FileResume(filename + ".temp")
        self.resume.add_block(0)

        self.data = ThreadSafeFile(filename, "wb+")

        try:
            self.temp = urlopen(remote_file, headers=headers)
        except:
            self.status = False
            self.close_handler()
            return
        myheaders = self.temp.info()

        if len(self.checksums) == 0:
            try:
                self.checksums = digest_parse(myheaders["Digest"])
            except KeyError:
                pass

        try:
            self.size = int(myheaders["Content-Length"])
        except (KeyError, TypeError):
            self.size = 0

        self.streamserver = None
        if PORT is not None:
            self.streamserver = StreamServer((HOST, PORT), StreamRequest)
            self.streamserver.set_stream(self.data)

            # thread.start_new_thread(self.streamserver.serve, ())
            mythread = threading.Thread(target=self.streamserver.serve)
            mythread.start()

    def close_handler(self):
        self.resume.complete()
        try:
            if PORT is None:
                self.data.close()
            self.temp.close()
        except:
            pass

        if self.status:
            self.status = filecheck(self.filename, self.checksums, self.size)

    def cycle(self):
        if self.oldtime is None:
            self.start_bitrate(self.counter * self.block_size)
        if self.cancel_handler is not None and self.cancel_handler():
            self.close_handler()
            return False

        block = self.temp.read(self.block_size)
        self.data.acquire()
        self.data.write(block)
        self.data.release()
        self.counter += 1
        self.total += len(block)

        self.resume.set_block_size(self.counter * self.block_size)

        if self.streamserver is not None:
            self.streamserver.set_length(self.counter * self.block_size)

        if self.status_handler is not None:
            self.status_handler(self.total, 1, self.size)

        if self.bitrate_handler is not None:
            self.bitrate_handler(self.get_bitrate(self.counter * self.block_size))

        if self.time_handler is not None:
            self.time_handler(self.get_time(self.counter * self.block_size))

        if not block:
            self.close_handler()

        # print self.get_bitrate(self.counter * self.block_size)
        return bool(block)


def filecheck(local_file, checksums, size, handler=None):
    if verify_checksum(local_file, checksums):
        act_size = 0
        try:
            act_size = os.stat(local_file).st_size
        except:
            pass

        if handler is not None:
            temp_size = size
            if size == 0:
                temp_size = act_size
            handler(1, act_size, temp_size)

        if int(act_size) == int(size) or size == 0:
            return True

    print("\n" + _("Checksum failed for %s.") % os.path.basename(local_file))
    return False


def parse_metalink(src, headers=None, nocheck=False, ver=3):
    if headers is None:
        headers = {}

    src = complete_url(src)
    is_metalink = nocheck

    # not all servers support HEAD where GET is also supported
    # also a WindowsError is thrown if a local file does not exist
    if src.endswith(".metalink") or src.endswith(".meta4"):
        is_metalink = True
    try:
        # add head check for metalink type, if MIME_TYPE or application/xml? treat as metalink
        my_headers = urlhead(src, metalink_header=True, headers=headers)
        if my_headers["content-type"].startswith(MIME_TYPE):
            print(_("Metalink content-type detected."))
            is_metalink = True
        elif my_headers["link"]:
            # Metalink HTTP Link headers implementation, RFC 6249
            # does not check for describedby urls but we can't use any of those anyway
            # TODO this should be more robust and ignore commas in <> for urls
            links = my_headers["link"].split(",")
            file_obj = metalink.MetalinkFile4(os.path.basename(src))
            file_obj.set_size(my_headers["content-length"])
            for link in links:
                parts = link.split(";")
                mydict = {}
                for part in parts[1:]:
                    part1, part2 = part.split("=", 1)
                    mydict[part1.strip()] = part2.strip()

                pri = ""
                try:
                    pri = mydict["pri"]
                except KeyError:
                    pass
                type_str = ""
                try:
                    type_str = mydict["type"]
                except KeyError:
                    pass
                try:
                    if (
                        mydict["rel"] == '"describedby"'
                        and type == "application/metalink4+xml"
                    ):
                        # TODO support metalink describedby type
                        # file_obj.add_url(parts[0].strip(" <>"), preference=pri)
                        pass
                    elif (
                        mydict["rel"] == '"describedby"'
                        and type == "application/pgp-signature"
                    ):
                        # support openpgp describedby type
                        fp = urlopen(parts[0].strip(" <>"), headers={"referer": src})
                        file_obj.hashlist["pgp"] = fp.read()
                        fp.close()
                    elif (
                        mydict["rel"] == '"describedby"'
                        or mydict["rel"] == '"duplicate"'
                    ):
                        file_obj.add_url(
                            parts[0].strip(" <>"), type=type_str, priority=pri
                        )
                except KeyError:
                    pass
            try:
                file_obj.hashlist = digest_parse(my_headers["digest"])
            except KeyError:
                # RFC requires link headers to be ignored if no digest header, use standard download method
                return False
            print(_("Using Metalink HTTP Link headers."))
            metalink4 = metalink.Metalink4()
            metalink4.files.append(file_obj)
            return metalink.convert(metalink4, ver)
    except KeyError:
        pass

    if not is_metalink:
        return False

    try:
        datasource = urlopen(src, metalink_header=True, headers=headers)
    except:
        return False

    metalink_obj = metalink.parsehandle(datasource, ver)
    datasource.close()
    return metalink_obj


def parse_rss(src, headers={}):
    src = complete_url(src)

    try:
        datasource = urlopen(src, headers=headers)
    except:
        return False

    rss_obj = metalink.RSSAtom()
    rss_obj.parsehandle(datasource)
    datasource.close()
    return rss_obj


def download_rss(
    src,
    path,
    force=False,
    handlers=None,
    segmented=SEGMENTED,
    headers=None,
    nocheck=False,
):
    if handlers is None:
        handlers = {}
    if headers is None:
        headers = {}

    rss_obj = parse_rss(src, headers)
    if not rss_obj:
        return False

    url_list = rss_obj.files
    if len(url_list) == 0:
        print(_("No enclosures to download files from."))
        return False

    results = []
    for rss_item in url_list:
        result = download_file(
            rss_item.url,
            os.path.join(path, os.path.basename(rss_item.url)),
            rss_item.size,
            force=force,
            handlers=handlers,
            segmented=segmented,
        )
        if result:
            results.append(result)

    if len(results) == 0:
        return False

    return results


def download_metalink(
    src,
    path,
    force=False,
    handlers=None,
    segmented=SEGMENTED,
    headers=None,
    nocheck=False,
):
    """
    Decode a metalink file, can be local or remote
    First parameter, file to download, URL, file path or Metalink object to download from
    Second parameter, file path to save to
    Third parameter, optional, force a new download even if a valid copy already exists
    Fourth parameter, optional, progress handler callback
    Returns list of file paths if download(s) is successful
    Returns None is the file is not a metalink file (parse_metalink output is False)
    Returns False otherwise (checksum fails)
    """
    if handlers is None:
        handlers = {}
    if headers is None:
        headers = {}

    my_headers = headers.copy()

    metalink_obj = parse_metalink(src, my_headers, nocheck)
    if not metalink_obj:
        return None

    if is_remote(src):
        my_headers["referer"] = src

    if metalink_obj.type == "dynamic":
        origin = metalink_obj.origin
        if origin != src and origin != "":
            print(_("Downloading update from %s") % origin)
            try:
                return download_metalink(
                    origin, path, force, handlers, segmented, my_headers
                )
            except:
                pass

    url_list = metalink_obj.files
    if len(url_list) == 0:
        print(_("No urls to download file from."))
        return False

    results = []
    for file_node in url_list:
        os_tag = file_node.os
        lang_tag = file_node.language

        if OS is None or len(os_tag) == 0 or os_tag[0].lower() == OS.lower():
            if "any" in LANG or len(lang_tag) == 0 or lang_tag.lower() in LANG:
                result = download_file_node(
                    file_node, path, force, handlers, segmented, my_headers
                )
                if result:
                    results.append(result)
    if len(results) == 0:
        return False

    return results


def download_jigdo(
    src, path, force=False, handlers=None, segmented=SEGMENTED, headers=None
):
    """
    Decode a jigdo file, can be local or remote
    First parameter, file to download, URL or file path to download from
    Second parameter, file path to save to
    Third parameter, optional, force a new download even if a valid copy already exists
    Fourth parameter, optional, progress handler callback
    Returns list of file paths if download(s) is successful
    Returns False otherwise (checksum fails)
    """
    if handlers is None:
        handlers = {}
    if headers is None:
        headers = {}

    new_src = complete_url(src)
    try:
        datasource = urlopen(new_src, metalink_header=True, headers=headers)
    except:
        return False

    jigdo = metalink.Jigdo()
    jigdo.parsehandle(datasource)
    datasource.close()

    # print path_join(src, jigdo.template)
    template = get(
        path_join(src, jigdo.template),
        path,
        {"md5": jigdo.template_md5},
        force,
        handlers,
        segmented,
        headers,
    )
    if not template:
        print(_("Could not download template file!"))
        return False

    url_list = jigdo.files
    if len(url_list) == 0:
        print(_("No urls to download file from."))
        return False

    results = []
    results.extend(template)
    for file_node in url_list:
        result = download_file_node(
            file_node, path, force, handlers, segmented, headers
        )
        if result:
            results.append(result)
    if len(results) == 0:
        return False

    print(_("Reconstituting file..."))
    md5 = jigdo.mkiso()
    checksum = verify_checksum(jigdo.filename, {"md5": md5})
    if not checksum:
        print(_("Checksum failed."))

    return results


def convert_jigdo(src, headers=None):
    """
    Decode a jigdo file, can be local or remote
    First parameter, file to download, URL or file path to download from
    Returns metalink xml text, False on error
    """
    if headers is None:
        headers = {}

    new_src = complete_url(src)
    try:
        datasource = urlopen(new_src, metalink_header=True, headers=headers)
    except:
        return False

    jigdo = metalink.Jigdo()
    jigdo.parsehandle(datasource)
    datasource.close()

    file_obj = metalink.MetalinkFile(jigdo.template)
    file_obj.add_url(os.path.dirname(src) + "/" + jigdo.template)
    file_obj.add_checksum("md5", jigdo.template_md5)
    jigdo.files.insert(0, file_obj)

    url_list = jigdo.files
    if len(url_list) == 0:
        print(_("No Jigdo data files!"))
        return False

    return jigdo.generate()


def download_file_node(
    item, path, force=False, handler=None, segmented=SEGMENTED, headers=None
):
    """
    First parameter, file XML node
    Second parameter, file path to save to
    Third parameter, optional, force a new download even if a valid copy already exists
    Fourth parameter, optional, progress handler callback
    Returns list of file paths if download(s) is successful
    Returns False otherwise (checksum fails)
    raise socket.error e.g. "Operation timed out"
    """
    if headers is None:
        headers = {}

    url_list = []
    for node in item.resources:
        url_list.append(node.url)

    if len(url_list) == 0:
        print(_("No urls to download file from."))
        return False

    local_file = item.filename
    item.filename = path_join(path, local_file)

    return download_file_urls(item, force, handler, segmented, headers)


def complete_url(url):
    """
    If no transport is specified in typical URL form, we assume it is a local
    file, perhaps only a relative path too.
    First parameter, string to convert to URL format
    Returns, string converted to URL format
    """
    if get_transport(url) == "":
        abs_file = os.path.abspath(url)
        if abs_file[0] != "/":
            abs_file = "/" + abs_file
        return "file://" + abs_file
    return url


def urlretrieve(url, filename, reporthook=None, headers=None):
    """Modernized replacement for urllib.urlretrieve() for use with proxy."""
    if headers is None:
        headers = {}

    block_size = 1024
    i = 0
    counter = 0
    temp = urlopen(url, headers=headers)
    my_headers = temp.info()

    try:
        size = int(my_headers["Content-Length"])
    except KeyError:
        size = 0

    data = open(filename, "wb")
    block = True

    ### FIXME need to check contents from previous download here
    resume = FileResume(filename + ".temp")
    resume.add_block(0)

    while block:
        block = temp.read(block_size)
        data.write(block)
        i += block_size
        counter += 1

        resume.set_block_size(counter * block_size)

        if reporthook is not None:
            reporthook(counter, block_size, size)

    resume.complete()

    data.close()
    temp.close()

    return filename, headers


class FileResume:
    """
    Manages the resume data file
    """

    def __init__(self, filename):
        self.size = 0
        self.blocks = []
        self.filename = filename
        self._read()

    def set_block_size(self, size):
        """
        Set the block size value without recomputing blocks
        """
        self.size = int(size)
        self._write()

    def update_block_size(self, size):
        """
        Recompute blocks based on new size
        """
        if self.size == size:
            return

        new_blocks = []
        count = 0
        total = 0
        offset = None

        for value in self.blocks:
            value = int(value)
            if value == count:
                if offset is None:
                    offset = count
                total += self.size
            elif offset is not None:
                start = (offset * self.size) / size
                new_blocks.extend(map(str, range(start, start + (total / size))))
                total = 0
                offset = None
            count += 1

        if offset is not None:
            start = int((offset * self.size) / size)
            # print(str, start, total, size)
            # print(range(start, int(start + (total / size))))
            new_blocks.extend(map(str, range(start, int(start + (total / size)))))

        self.blocks = new_blocks
        self.set_block_size(size)

    def start_byte(self):
        """
        Returns byte to start at, all previous are OK
        """
        if len(self.blocks) == 0:
            return 0

        count = 0
        for value in self.blocks:
            if int(value) != count:
                return (count + 1) * self.size
            count += 1

        return None

    def add_block(self, block_id):
        """
        Add a block to list of completed
        """
        if str(block_id) not in self.blocks:
            self.blocks.append(str(block_id))
        self._write()

    def remove_block(self, block_id):
        """
        Remove a block from list of completed
        """
        self.blocks.remove(str(block_id))
        self._write()

    def clear_blocks(self):
        """
        Remove all blocks from completed list
        """
        self.blocks = []
        self._write()

    def extend_blocks(self, blocks):
        """
        Replace the list of block ids
        """
        for block in blocks:
            if str(block) not in self.blocks:
                self.blocks.append(str(block))
        self._write()

    def _write(self):
        filehandle = open(self.filename, "w")
        filehandle.write("%s:" % str(self.size))
        # for block_id in self.blocks:
        # filehandle.write(str(block_id) + ",")
        # print self.blocks
        filehandle.write(",".join(self.blocks))
        filehandle.close()

    def _read(self):
        try:
            filehandle = open(self.filename)
            resume_str = filehandle.readline()
            (size, blocks) = resume_str.split(":")
            self.blocks = blocks.split(",")
            self.size = int(size)
            filehandle.close()
        except (OSError, ValueError):
            self.blocks = []
            self.size = 0

    def complete(self):
        """
        Download completed, remove block count file
        """
        os.remove(self.filename)


def verify_chunk_checksum(chunkstring, checksums=None):
    """
    Verify the checksum of a file
    First parameter, filename
    Second parameter, optional, expected dictionary of checksums
    Returns True if first checksum provided is valid
    Returns True if no checksums are provided
    Returns False otherwise
    """
    if checksums is None:
        checksums = {}

    hash_algorithms = ["sha512", "sha384", "sha256", "sha1", "md5"]

    for algorithm in hash_algorithms:
        try:
            if checksums.get(algorithm):
                hash_obj = hashlib.new(algorithm)
                hash_obj.update(chunkstring)
                if hash_obj.hexdigest() == checksums[algorithm].lower():
                    return True
                else:
                    return False
        except (KeyError, AttributeError):
            pass

    # No checksum provided, assume OK
    return True


def verify_checksum(local_file, checksums=None):
    """
    Verify the checksum of a file
    First parameter, filename
    Second parameter, optional, expected dictionary of checksums
    Returns True if first checksum provided is valid
    Returns True if no checksums are provided
    Returns False otherwise
    """
    if checksums is None:
        checksums = {}

    try:
        return pgp_verify_sig(local_file, checksums["pgp"])
    except (KeyError, AttributeError, ValueError, AssertionError):
        pass
    try:
        checksums["sha512"]
        if filehash(local_file, hashlib.sha512()) == checksums["sha512"].lower():
            return True
        else:
            # print "\nERROR: sha512 checksum failed for %s." % os.path.basename(local_file)
            return False
    except (KeyError, AttributeError):
        pass
    try:
        checksums["sha384"]
        if filehash(local_file, hashlib.sha384()) == checksums["sha384"].lower():
            return True
        else:
            # print "\nERROR: sha384 checksum failed for %s." % os.path.basename(local_file)
            return False
    except (KeyError, AttributeError):
        pass
    try:
        checksums["sha256"]
        if filehash(local_file, hashlib.sha256()) == checksums["sha256"].lower():
            return True
        else:
            # print "\nERROR: sha256 checksum failed for %s." % os.path.basename(local_file)
            return False
    except (KeyError, AttributeError):
        pass
    try:
        checksums["sha1"]
        if filehash(local_file, hashlib.sha1()) == checksums["sha1"].lower():
            return True
        else:
            # print "\nERROR: sha1 checksum failed for %s." % os.path.basename(local_file)
            return False
    except KeyError:
        pass
    try:
        checksums["md5"]
        if filehash(local_file, hashlib.md5()) == checksums["md5"].lower():
            return True
        else:
            # print "\nERROR: md5 checksum failed for %s." % os.path.basename(local_file)
            return False
    except KeyError:
        pass

    # No checksum provided, assume OK
    return True


def pgp_verify_sig(filename, sig):
    gpg = GPG.GPGSubprocess(keyring=PGP_KEY_STORE)

    for root, dirs, files in os.walk(PGP_KEY_DIR):
        for this_file in files:
            if this_file[-4:] in PGP_KEY_EXTS:
                gpg.import_key(open(this_file).read())

    sign = gpg.verify_file_detached(filename, sig)

    print("\n-----" + _("BEGIN PGP SIGNATURE INFORMATION") + "-----")
    if sign.error is not None:
        print(sign.error)
    else:
        # print sig.creation_date
        try:
            print(
                "" + _("timestamp") + ":",
                time.strftime(
                    "%a, %d %b %Y %H:%M:%S (%Z)", time.localtime(float(sign.timestamp))
                ),
            )
        except TypeError:
            pass
        print("" + _("fingerprint") + ":", sign.fingerprint)
        # print sig.signature_id
        # print sign.key_id
        print("" + _("uid") + ":", sign.username)
    print("-----" + _("END PGP SIGNATURE INFORMATION") + "-----\n")

    if sign.error is not None:
        raise AssertionError(sign.error)

    if sign.is_valid():
        return True

    return False


def is_remote(name):
    transport = get_transport(name)

    if transport != "":
        return True
    return False


def is_local(name):
    transport = get_transport(name)

    if transport == "":
        return True
    return False


def get_transport(url):
    """
    Gets transport type.  This is more accurate than the urlparse module which
    just does a split on colon.
    First parameter, url
    Returns the transport type
    """
    url = str(url)
    result = url.split("://", 1)
    if len(result) == 1:
        transport = ""
    else:
        transport = result[0]
    return transport


def filehash(thisfile, filesha):
    """
    First parameter, filename
    Returns SHA1 sum as a string of hex digits
    """
    try:
        filehandle = open(thisfile, "rb")
    except:
        return ""

    chunk_size = 1024 * 1024
    data = filehandle.read(chunk_size)
    while data != b"":
        filesha.update(data)
        data = filehandle.read(chunk_size)

    filehandle.close()
    return filesha.hexdigest()


def path_join(first, second):
    """
    A function that is called to join two paths, can be URLs or filesystem paths
    Parameters, two paths to be joined
    Returns new URL or filesystem path
    """
    if first == "":
        return second
    if is_remote(second):
        return second

    if is_remote(first):
        if is_local(second):
            return urllib.parse.urljoin(first, second)
        return second

    return os.path.normpath(os.path.join(first, second))


def start_sort(urldict):
    urls = copy.deepcopy(urldict)
    local_urls = {}
    if COUNTRY is not None:
        for url in list(urls):
            if COUNTRY.lower() == urls[url].location.lower():
                local_urls[url] = urls[url]
                urls.pop(url)

    new_urls = sort_prefs(local_urls)
    new_urls.extend(sort_prefs(urls))
    return new_urls


def sort_prefs(mydict):
    new_urls = []

    for url in list(mydict):
        new_urls.append((mydict[url].preference, mydict[url].url))

    new_urls.sort()
    new_urls.reverse()

    result = []
    for url in new_urls:
        result.append(url[1])
    return result


############# segmented download functions #############


class ThreadSafeFile(io.FileIO):
    def __init__(self, *args):
        io.FileIO.__init__(self, *args)
        self.lock = threading.Lock()

    def acquire(self):
        return self.lock.acquire()

    def release(self):
        return self.lock.release()


class Segment_Manager(Manager):
    def __init__(self, metalinkfile, headers={}):
        Manager.__init__(self)

        self.headers = headers.copy()
        self.sockets = []
        self.chunks: List[Http_Host_Segment] = []
        self.limit_per_host = LIMIT_PER_HOST
        self.host_limit = HOST_LIMIT
        # self.size = 0
        # if metalinkfile.size != "":
        self.size = metalinkfile.get_size()
        self.orig_urls = metalinkfile.get_url_dict()
        self.urls = self.orig_urls
        self.chunk_size = int(metalinkfile.piecelength)
        self.chunksums = metalinkfile.get_piece_dict()
        self.checksums = metalinkfile.hashlist
        self.localfile = metalinkfile.filename
        self.filter_urls()

        self.status = True

        # Open the file.
        try:
            self.f = ThreadSafeFile(self.localfile, "rb+")
        except OSError:
            self.f = ThreadSafeFile(self.localfile, "wb+")

        self.resume = FileResume(self.localfile + ".temp")

        self.streamserver = None
        if PORT is not None:
            self.streamserver = StreamServer((HOST, PORT), StreamRequest)
            self.streamserver.set_stream(self.f)

            # thread.start_new_thread(self.streamserver.serve, ())
            my_thread = threading.Thread(target=self.streamserver.serve)
            my_thread.start()

    def get_chunksum(self, index):
        my_list = {}
        try:
            for key in self.chunksums.keys():
                my_list[key] = self.chunksums[key][index]
        except (KeyError, IndexError):
            pass

        return my_list

    def get_size(self):
        """
        Take a best guess at size based on first 3 matching servers

        raise socket.error e.g. "Operation timed out"
        """
        i = 0
        sizes = []
        checksums = []
        urls = list(self.urls)

        while i < len(urls) and (len(sizes) < 3):
            url = urls[i]
            protocol = get_transport(url)
            if protocol == "http":
                status = http.client.MOVED_PERMANENTLY
                count = 0
                size = None
                checksum_dict = {}
                while (
                    status == http.client.MOVED_PERMANENTLY
                    or status == http.client.FOUND
                ) and count < MAX_REDIRECTS:
                    http_host = Http_Host(url)
                    if http_host.conn is not None:
                        try:
                            headers = {"Want-Digest": DIGESTS}
                            headers.update(self.headers)
                            http_host.conn.request("HEAD", url, headers=headers)
                            response = http_host.conn.getresponse()
                            status = response.status
                            url = response.getheader("Location")
                            size = response.getheader("content-length")
                            checksum_dict = digest_parse(
                                response.getheader("Digest", None)
                            )
                        except:
                            pass
                        http_host.close()
                    count += 1

                if (status == http.client.OK) and (size is not None):
                    sizes.append(size)
                    if len(checksum_dict) > 0:
                        checksums.append(checksum_dict)

            elif protocol == "ftp":
                ftp = Ftp_Host(url)

                try:
                    size = ftp.conn.size(url)
                except ftplib.error_perm:
                    size = None

                if size is not None:
                    sizes.append(size)

            i += 1

        if len(self.checksums) == 0 and len(checksums) > 0:
            if len(checksums) == 1:
                self.checksums = checksums[0]
            if checksums.count(checksums[0]) >= 2:
                self.checksums = checksums[0]
            if checksums.count(checksums[1]) >= 2:
                self.checksums = checksums[1]

        if len(sizes) == 0:
            return None
        if len(sizes) == 1:
            return int(sizes[0])
        if sizes.count(sizes[0]) >= 2:
            return int(sizes[0])
        if sizes.count(sizes[1]) >= 2:
            return int(sizes[1])

        return None

    def filter_urls(self):
        new_urls = {}
        for item in list(self.urls.keys()):
            if (not item.endswith(".torrent")) and (get_transport(item) in PROTOCOLS):
                new_urls[item] = self.urls[item]
        self.urls = new_urls
        return new_urls

    def run(self, wait=0.1):
        """
        ?
        """
        # try:
        if self.size == "" or self.size == 0:
            self.size = self.get_size()
            if self.size is None:
                # crap out and do it the old way
                self.close_handler()
                self.status = False
                return False

        # can't adjust chunk size if it has chunk hashes tied to that size
        if len(self.chunksums) == 0 and self.size / self.chunk_size > MAX_CHUNKS:
            self.chunk_size = self.size / MAX_CHUNKS
            # print "Set chunk size to %s." % self.chunk_size
        self.resume.update_block_size(self.chunk_size)

        return Manager.run(self, wait)

    def cycle(self):
        """
        Runs one cycle
        Returns True if still downloading, False otherwise
        """
        try:
            # Renamed to _bytes to not overshadow built-in bytes
            _bytes = self.byte_total()

            index = self.get_chunk_index()
            if index is not None and index > 0 and self.streamserver is not None:
                self.streamserver.set_length((index - 1) * self.chunk_size)

            if self.oldtime is None:
                self.start_bitrate(_bytes)

            # cancel was pressed here
            if self.cancel_handler is not None and self.cancel_handler():
                self.status = False
                self.close_handler()
                return False

            self.update()
            self.resume.extend_blocks(self.chunk_list())

            if _bytes >= self.size and self.active_count() == 0:
                self.resume.complete()
                self.close_handler()
                return False

            # crap out and do it the old way
            if len(self.urls) == 0:
                self.status = False
                self.close_handler()
                return False

            return True

        except KeyboardInterrupt:
            print("Download Interrupted!")
            self.close_handler()
            return False

    def update(self):
        if self.status_handler is not None and self.size is not None:
            # count = int(self.byte_total()/self.chunk_size)
            # if self.byte_total() % self.chunk_size:
            #    count += 1
            # self.status_handler(count, self.chunk_size, self.size)
            self.status_handler(self.byte_total(), 1, self.size)
        if self.bitrate_handler is not None:
            self.bitrate_handler(self.get_bitrate(self.byte_total()))
        if self.time_handler is not None:
            self.time_handler(self.get_time(self.byte_total()))

        # Rename to _next to not overshadow built-in next
        _next = self.next_url()

        if _next is None:
            return

        index = self.get_chunk_index()
        if index is not None:
            start = index * self.chunk_size
            end = start + self.chunk_size
            if end > self.size:
                end = self.size

            if _next.protocol == "http" or _next.protocol == "https":
                segment = Http_Host_Segment(
                    _next, start, end, self.size, self.get_chunksum(index), self.headers
                )
                segment.set_cancel_callback(self.cancel_handler)
                self.chunks[index] = segment
                self.segment_init(index)
            if _next.protocol == "ftp":
                # print "allocated to:", index, next.url
                segment = Ftp_Host_Segment(
                    _next, start, end, self.size, self.get_chunksum(index)
                )
                segment.set_cancel_callback(self.cancel_handler)
                self.chunks[index] = segment
                self.segment_init(index)

    def segment_init(self, index):
        segment = self.chunks[index]
        if str(index) in self.resume.blocks:
            segment.end()
            if segment.error is None:
                segment.bytes = segment.byte_count
            else:
                self.resume.remove_block(index)
        else:
            segment.start()

    def get_chunk_index(self):
        i = -1
        for i in range(len(self.chunks)):
            if self.chunks[i] is None or self.chunks[i].error is not None:
                return i
            # weed out dead segments that have temp errors and reassign
            if not self.chunks[i].is_alive() and self.chunks[i].bytes == 0:
                return i
        i += 1

        if (i * self.chunk_size) < self.size:
            self.chunks.append(None)
            return i

        return None

    def gen_count_array(self):
        temp = {}
        for item in self.sockets:
            try:
                temp[item.url] += 1
            except KeyError:
                temp[item.url] = 1
        return temp

    def active_count(self):
        count = 0
        for item in self.chunks:
            if item.is_alive():
                count += 1
        return count

    def next_url(self):
        """returns next socket to use or None if none available"""
        self.remove_errors()

        if (len(self.sockets) >= (self.host_limit * self.limit_per_host)) or (
            len(self.sockets) >= (self.limit_per_host * len(self.urls))
        ):
            # We can't create any more sockets, but we can see what's available
            # print "existing sockets"
            for item in self.sockets:
                # print item.active, item.url
                if not item.get_active():
                    return item
            return None

        count = self.gen_count_array()
        # randomly start with a url index
        # urls = list(self.urls)
        # number = int(random.random() * len(self.urls))
        urls = start_sort(self.urls)
        number = 0

        countvar = 1
        while countvar <= len(self.urls):
            try:
                temp_count = count[urls[number]]
            except KeyError:
                temp_count = 0
            # check against limits
            if ((temp_count == 0) and (len(count) < self.host_limit)) or (
                0 < temp_count < self.limit_per_host
            ):
                # check protocol type here
                protocol = get_transport(urls[number])
                if (not urls[number].endswith(".torrent")) and (
                    protocol == "http" or protocol == "https"
                ):
                    host = Http_Host(urls[number], self.f)
                    self.sockets.append(host)
                    return host
                if protocol == "ftp":
                    try:
                        host = Ftp_Host(urls[number], self.f)
                    except (
                        socket.gaierror,
                        socket.timeout,
                        ftplib.error_temp,
                        ftplib.error_perm,
                        OSError,
                    ):
                        self.urls.pop(urls[number])
                        return None
                    self.sockets.append(host)
                    return host

            number = (number + 1) % len(self.urls)
            countvar += 1

        return None

    def remove_errors(self):
        for item in self.chunks:
            if item is not None and item.error is not None:
                if (
                    item.error == http.client.MOVED_PERMANENTLY
                    or item.error == http.client.FOUND
                ):
                    try:
                        new_item = copy.deepcopy(self.urls[item.url])
                        new_item.url = item.location
                        self.urls[item.location] = new_item
                    except KeyError:
                        pass
                    self.filter_urls()

                try:
                    self.urls.pop(item.url)
                except KeyError:
                    pass

        for socket_item in self.sockets:
            if socket_item.url not in self.urls.keys():
                self.sockets.remove(socket_item)

        return

    def byte_total(self):
        total = 0
        count = 0
        for item in self.chunks:
            try:
                if item.error is None:
                    total += item.bytes
            except AttributeError:
                pass
            count += 1
        return total

    def chunk_list(self):
        chunks = []
        for i in range(len(self.chunks)):
            # print i, self.chunks[i].bytes
            try:
                if self.chunks[i].bytes == self.chunk_size:
                    chunks.append(i)
            except AttributeError:
                pass
        # print chunks
        return chunks

    def close_handler(self):
        if PORT is None:
            self.f.close()
        for host in self.sockets:
            host.close()

        self.update()

        # try:
        size = int(os.stat(self.localfile).st_size)
        if size == 0:
            try:
                os.remove(self.localfile)
                os.remove(self.localfile + ".temp")
            except OSError:
                pass
            self.status = False
        elif self.status:
            self.status = filecheck(self.localfile, self.checksums, size)
        # except: pass


class Host_Base:
    """
    Base class for various host protocol types.  Not to be used directly.
    """

    def __init__(self, url, memmap):
        self.bytes = 0
        self.ttime = 0
        self.start_time = None
        self.error = None
        self.conn = None
        self.active = False

        self.url = url
        self.mem = memmap

        transport = get_transport(self.url)
        self.protocol = transport

    def import_stats(self, segment):
        pass

    def set_active(self, value):
        self.active = value

    def get_active(self):
        return self.active


class Ftp_Host(Host_Base):
    def __init__(self, url, memmap=None):
        Host_Base.__init__(self, url, memmap)

        self.connect()

    def connect(self):
        if self.protocol == "ftp":
            url_parts = urllib.parse.urlsplit(self.url)
            try:
                username = url_parts.username
                password = url_parts.password
            except AttributeError:
                # needed for python < 2.5
                username = None

            if username is None:
                username = "anonymous"
                password = "anonymous"
            try:
                port = url_parts.port
            except:
                port = ftplib.FTP_PORT
            if port is None:
                port = ftplib.FTP_PORT

            self.conn = proxy.FTP()
            self.conn.connect(url_parts[1], port)
            try:
                self.conn.login(username, password)
            except:
                raise
            # set to binary mode, only works when not proxied
            try:
                self.conn.voidcmd("TYPE I")
            except:
                pass
        else:
            self.error = _("unsupported protocol")
            raise AssertionError
            # return

    def close(self):
        if self.conn is not None:
            try:
                self.conn.quit()
            except:
                pass

    def reconnect(self):
        self.close()
        self.connect()


class Http_Host(Host_Base):
    def __init__(self, url, memmap=None):
        Host_Base.__init__(self, url, memmap)

        url_parts = urllib.parse.urlsplit(self.url)
        if self.url.endswith(".torrent"):
            self.error = _("unsupported protocol")
            return
        elif self.protocol == "http":
            try:
                port = url_parts.port
            except:
                port = http.client.HTTP_PORT
            if port is None:
                port = http.client.HTTP_PORT
            try:
                self.conn = proxy.HTTPConnection(url_parts[1], port)
            except http.client.InvalidURL:
                self.error = _("invalid url")
                return
        elif self.protocol == "https":
            try:
                port = url_parts.port
            except:
                port = http.client.HTTPS_PORT
            if port is None:
                port = http.client.HTTPS_PORT
            try:
                self.conn = proxy.HTTPSConnection(url_parts[1], port)
            except http.client.InvalidURL:
                self.error = _("invalid url")
                return
        else:
            self.error = _("unsupported protocol")
            return

    def close(self):
        if self.conn is not None:
            self.conn.close()


class Host_Segment:
    """
    Base class for various segment protocol types.  Not to be used directly.
    """

    def __init__(self, host, start, end, filesize, checksums=None, headers=None):
        threading.Thread.__init__(self)

        if checksums is None:
            checksums = {}
        if headers is None:
            headers = {}

        self.host = host
        self.host.set_active(True)
        self.byte_start = start
        self.byte_end = end
        self.byte_count = end - start
        self.filesize = filesize
        self.url = host.url
        self.mem = host.mem
        self.checksums = checksums
        self.error = None
        self.ttime = 0
        self.response = None
        self.bytes = 0
        self.buffer = b""
        self.temp = ""
        self.cancel_handler = None
        self.headers = headers.copy()

    def set_cancel_callback(self, handler):
        self.cancel_handler = handler

    def check_cancel(self):
        if self.cancel_handler is None:
            return False
        return self.cancel_handler()

    def avg_bitrate(self):
        bits = self.bytes * 8
        return bits / self.ttime

    def checksum(self):
        if self.check_cancel():
            return False

        try:
            self.mem.acquire()
            self.mem.seek(self.byte_start, 0)
            chunk_str = self.mem.read(self.byte_count)
            self.mem.release()
        except ValueError:
            return False

        return verify_chunk_checksum(chunk_str, self.checksums)

    def close(self):
        if self.error is not None:
            self.host.close()

        self.host.set_active(False)

    def end(self):
        if self.error is None and not self.checksum():
            self.error = _("Chunk checksum failed")
        self.close()


class Ftp_Host_Segment(threading.Thread, Host_Segment):
    def __init__(self, *args):
        threading.Thread.__init__(self)
        Host_Segment.__init__(self, *args)

    def run(self):
        # Finish early if checksum is OK
        if self.checksum() and len(self.checksums) > 0:
            self.bytes += self.byte_count
            self.close()
            return

        # check for supported hosts/urls
        url_parts = urllib.parse.urlsplit(self.url)
        if self.host.conn is None:
            # print "bad socket"
            self.error = _("bad socket")
            self.close()
            return

        size = None
        retry = True
        count = 0
        while retry and count < CONNECT_RETRY_COUNT:
            retry = False
            try:
                (self.response, size) = self.host.conn.ntransfercmd(
                    "RETR " + url_parts.path, self.byte_start, self.byte_end
                )
            except ftplib.error_perm as error:
                self.error = error.message
                self.close()
                return
            except (socket.gaierror, socket.timeout) as error:
                self.error = error.args
                self.close()
                return
            except EOFError:
                self.error = _("EOFError")
                self.close()
                return
            except AttributeError:
                self.error = _("AttributeError")
                self.close()
                return
            except OSError:
                try:
                    self.host.reconnect()
                except:
                    pass
                retry = True
                count += 1
            except ftplib.error_temp as error:
                # this is not an error condition, most likely transfer TCP connection was closed
                # count += 1
                # self.error = "error temp", error.message
                self.temp = error.message
                self.close()
                return
            except ftplib.error_reply:
                # this is likely just an extra chatty FTP server, ignore for now
                pass

            if count >= CONNECT_RETRY_COUNT:
                self.error = _("socket reconnect attempts failed")
                self.close()
                return

        if size is not None:
            if self.filesize != size:
                self.error = _("bad file size")
                return

        self.start_time = time.time()
        while True:
            if self.readable():
                self.handle_read()
                self.ttime += time.time() - self.start_time
            else:
                self.end()
                return

    def readable(self):
        if self.check_cancel():
            return False

        if self.response is None:
            return False
        return True

    def handle_read(self):
        try:
            data = self.response.recv(1024)
        except socket.timeout:
            self.error = _("read timeout")
            self.response = None
            return

        if len(data) == 0:
            return

        self.buffer += data
        # print len(self.buffer), self.byte_count
        if len(self.buffer) >= self.byte_count:
            # When using a HTTP proxy there is no shutdown() call
            try:
                self.response.shutdown(socket.SHUT_RDWR)
            except AttributeError:
                pass

            temp_buffer = self.buffer[: self.byte_count]
            self.buffer = b""

            self.bytes += len(temp_buffer)

            try:
                self.mem.acquire()
                self.mem.seek(self.byte_start, 0)
                self.mem.write(temp_buffer)
                self.mem.flush()
                self.mem.release()
            except ValueError:
                self.error = _("bad file handle")

            self.response = None

        # this method writes directly to file on each data grab, not working for some reason


##        if (self.bytes + len(data)) >= self.byte_count:
##            # When using a HTTP proxy there is no shutdown() call
##            try:
##                self.response.shutdown(socket.SHUT_RDWR)
##            except AttributeError:
##                pass
##
##            index = self.byte_count - (self.bytes + len(data))
##
##            writedata = data[:index]
##
##            self.mem.acquire()
##            self.mem.seek(self.byte_start + self.bytes, 0)
##            self.mem.write(writedata)
##            self.mem.flush()
##
##            self.mem.release()
##
##            self.response = None
##        else:
##            writedata = data
##
##            lock = threading.Lock()
##            lock.acquire()
##
##            self.mem.seek(self.byte_start + self.bytes, 0)
##            self.mem.write(writedata)
##
##            lock.release()
##
##        self.bytes += len(writedata)


class Http_Host_Segment(threading.Thread, Host_Segment):
    def __init__(self, *args):
        threading.Thread.__init__(self)
        Host_Segment.__init__(self, *args)

    def run(self):
        # try:
        # Finish early if checksum is OK
        if self.checksum() and len(self.checksums) > 0:
            self.bytes += self.byte_count
            self.close()
            return

        if self.host.conn is None:
            self.error = _("bad socket")
            self.close()
            return

        try:
            self.headers.update(
                {"Range": "bytes=%lu-%lu" % (self.byte_start, self.byte_end - 1)}
            )
            self.host.conn.request("GET", self.url, "", self.headers)
        except (OSError, socket.herror, socket.gaierror, socket.timeout):
            self.error = _("socket exception")
            self.close()
            return

        self.start_time = time.time()
        while True:
            if self.readable():
                self.handle_read()
                self.ttime += time.time() - self.start_time
            else:
                self.end()
                return

    # except BaseException, e:
    #    self.error = utils.get_exception_message(e)

    def readable(self):
        if self.check_cancel():
            return False

        if self.response is None:
            try:
                self.response = self.host.conn.getresponse()
            except socket.timeout:
                self.error = _("timeout")
                return False
            # not an error state, connection closed, kicks us out of thread
            except http.client.ResponseNotReady:
                return False
            except:
                self.error = _("response error")
                return False

        if self.response.status == http.client.PARTIAL_CONTENT:
            return True
        elif (
            self.response.status == http.client.MOVED_PERMANENTLY
            or self.response.status == http.client.FOUND
        ):
            self.location = self.response.getheader("Location")
            self.error = self.response.status
            self.response = None
            return False
        else:
            self.error = self.response.status
            self.response = None
            return False

    def handle_read(self):
        try:
            data = self.response.read()
        except socket.timeout:
            self.error = _("timeout")
            self.response = None
            return
        except http.client.IncompleteRead:
            self.error = _("incomplete read")
            self.response = None
            return
        except OSError:
            self.error = _("socket error")
            self.response = None
            return
        except TypeError:
            self.response = None
            return

        if len(data) == 0:
            return

        range_str = self.response.getheader("Content-Range")
        request_size = int(range_str.split("/")[1])

        if request_size != self.filesize:
            self.error = _("bad file size")
            self.response = None
            return

        # Check digest headers against expected
        digest = self.response.getheader("Digest", None)
        if digest is not None:
            digest_sums = digest_parse(digest)
            # check digest here, skip if missing, return if mismatch
            for hashtype in self.checksums.keys():
                try:
                    digest_sums[hashtype]
                except KeyError:
                    continue

                if self.checksums[hashtype] != digest_sums[hashtype]:
                    return

        body = data
        size = len(body)

        # write out body to file
        try:
            self.mem.acquire()
            self.mem.seek(self.byte_start + self.bytes, 0)
            self.mem.write(body)
            self.mem.flush()
            self.mem.release()
        except ValueError:
            self.error = _("bad file handle")
            self.response = None
            return

        self.bytes += size
        # print self.bytes, self.byte_count
        if self.bytes >= self.byte_count:
            self.response = None


class StreamRequest(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        start = 0
        while True:
            if self.server.fileobj is not None and (self.server.length - start) > 0:
                try:
                    self.server.fileobj.acquire()
                    loc = self.server.fileobj.tell()
                    self.server.fileobj.seek(start, 0)
                    size = self.server.length - start

                    data = self.server.fileobj.read(size)
                    if len(data) > 0:
                        self.wfile.write(data)

                    self.server.fileobj.seek(loc, 0)
                    self.server.fileobj.release()
                    start += len(data)
                except ValueError:
                    break
            time.sleep(0.1)


class StreamServer(http.server.HTTPServer):
    def __init__(self, *args):
        http.server.HTTPServer.__init__(self, *args)
        self.fileobj = None
        self.length = 0
        self.run = False

    # based on: http://code.activestate.com/recipes/425210/
    def server_bind(self):
        http.server.HTTPServer.server_bind(self)
        self.socket.setblocking(False)
        self.socket.settimeout(1)
        self.run = True

    def get_request(self):
        while self.run:
            try:
                sock, addr = self.socket.accept()
                sock.setblocking(False)
                sock.settimeout(30)
                return sock, addr
            except socket.timeout:
                pass

    def stop(self):
        self.run = False

    def serve(self):
        try:
            while self.run:
                self.handle_request()
        except KeyboardInterrupt:
            print("Server Interrupted!")
            self.fileobj.close()
            self.stop()

    def set_stream(self, fileobj):
        self.fileobj = fileobj

    def set_length(self, length):
        self.length = int(length)


# if __name__=="__main__":
# testurls = ("ftp://ftp.freebsd.org/pub/FreeBSD/README.TXT", "http://www.google.com", "https://encrypted.google.com")
# #testurls = ("http://www.google.com", "https://encrypted.google.com")
# # for testfile in testurls:
# # files = get(testfile, os.getcwd(), force=True, segmented=False)
# # print "Downloaded:", files

# # print "=" * 79

# # for testfile in testurls:
# # files = get(testfile, os.getcwd(), force=True, segmented=True)
# # print "Downloaded:", files

# # print "=" * 79

# proxystr = "http://localhost:8000"
# proxy.HTTP_PROXY = proxystr
# proxy.HTTPS_PROXY = proxystr
# proxy.FTP_PROXY = proxystr
# proxy.set_proxies()

# # for testfile in testurls:
# # files = get(testfile, os.getcwd(), force=True, segmented=False)
# # print "Downloaded:", files

# # print "=" * 79

# for testfile in testurls:
# files = get(testfile, os.getcwd(), force=True, segmented=True)
# print "Downloaded:", files

##myserver = StreamServer(("localhost", 8080), StreamRequest)
##myserver.set_stream(ThreadSafeFile("C:\\library\\avril\\Avril Lavigne - Complicated.mpg", "rb"))
##myserver.set_length(50000000)
##serverthread = threading.Thread(target=myserver.serve_forever)
##serverthread.start()

# myserver.serve_forever()
