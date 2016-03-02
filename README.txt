#!/usr/bin/env python
########################################################################
#
# Project: pyMetalink
# URL: https://github.com/metalink-dev/pymetalink
# E-mail: nabber00@gmail.com
#
# Copyright: (C) 2007-2016, Neil McNab, Hampus Wessman
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
#   pyMetalink is a library for python to support advanced download features
#
# Example:
#
# import metalink.download
#
# files = metalink.download.get("file.metalink", os.getcwd())
#
# CHANGELOG:
#
# Version 6.2
# -----------
# - Tested
# - Initial Python 3.x support
# - License change to MIT approved by all authors, can still be combined with GPL software
# - Catches GPG NEWSIG response
#
# Version 6.1
# -----------
# - Packaged as pure Python package for easy_install and pip
# 
# Version 6.0
# -----------
# - Support for RFC 3230 - Instance Digests in HTTP
# - Support for RFC 6249 - Metalink/HTTP: Mirrors and Hashes
#
# Version 5.1
# -----------
# - Bugfixes for segmented downloads
# - Native Jigdo download support
# - Added download time
# - Now requires Python 2.5 or newer because Metalink RFC requires SHA-256
#
# Version 5.0
# -----------
# - Added support for Metalink v4 (IETF RFC)
#
# Version 4.4
# -----------
# - Bugfix for when HTTP 302 redirect code is issued during download
#
# Version 4.3
# -----------
# - Added custom HTTP header support
# - Added option to parse an HTML file for .metalink files to check
# - Added a beta feature for media streaming
# - Various bugfixes
#
# Version 4.2
# -----------
# - PGP bugfix
# - Jigdo to Metalink convertor
# - Other bugfixes
#
# Version 4.1
# -----------
# - XML parsing speed and memory improvements
# - Checking function is now multithreaded for speed improvements
# - Displays download bitrates
# - Grabs proxy info from environment variables and Windows registry
# - Fix for faulty file locking, this causes corrupted downloads
#
# Version 4.0
# -----------
# - Uses gzip compression when available on server (non-segmented downloads only)
# - Fixed memory leak when computing a checksum
# - Bugfixes for download resuming
#
# Version 3.8
# -----------
# - Will now download any file type and auto-detect metalink files
# - Added support for metalink "Accept" HTTP header
#
# Version 3.7.4
# -------------
# - Fixed default key import directory
#
# Version 3.7.3
# -------------
# - Fixes for use with UNIX/Linux
# - bugfixes in checker code
#
# Version 3.7.2
# -------------
# - Modified to remove the pyme dependency
#
# Version 3.7.1
# -------------
# - Removed missing imports
#
# Version 3.7
# -----------
# - Added first attempt at PGP signature checking
# - Minor bugfixes
#
# Version 3.6
# -----------
# - Support for resuming segmented downloads
# - Modified for better Python 2.4 support
#
# Version 3.5
# -----------
# - Code cleanup
# - FTP close connection speed improvement
# - Added documentation for how to use as a library
# - Sort by country pref first (if set), then pref value in metalink
# 
# Version 3.4
# -----------
# - segmented download FTP size support
# - support for user specified OS and language preferences
# - finished FTP proxy support
#
# Version 3.3
# -----------
# - Bugfix for when type attr not present
# - Support for FTP segmented downloads
#
# Version 3.2
# -----------
# - If type="dynamic", client checks origin location
#
# Version 3.1
# -----------
# - Now handles all SHA hash types and MD5
# - Minor bug fixes
#
# Version 3.0
# -----------
# - Speed and bandwidth improvements for checking mode
# - Added checking of chunk checksums
# - If chunk checksums are present, downloads are resumed
# - Proxy support (experimental, HTTP should work, FTP and HTTPS not likely)
#
# Version 2.0.1
# -------------
# - Bugfix when doing size check on HTTP servers, more reliable now
#
# Version 2.0
# -----------
# - Support for segmented downloads! (HTTP urls only, falls back to old method if only FTP urls)
#
# Version 1.4
# -----------
# - Added support for checking the file size on FTP servers
#
# Version 1.3.1
# -------------
# - Made error when XML parse fails a little clearer.
#
# Version 1.3
# -----------
# - Fixed bug when no "size" attribute is present
#
# Version 1.2
# -----------
# - Added totals output
#
# Version 1.1
# -----------
# - Bugfixes for FTP handling, bad URL handling
# - rsync doesn't list as a URL Error
# - reduced timeout value
#
# Version 1.0
# -----------
# This is the initial release.
#
# TODO
# - resume download support for non-segmented downloads
# - download priority based on speed
# - use maxconnections
# - dump FTP data chunks directly to file instead of holding in memory
# 
########################################################################
