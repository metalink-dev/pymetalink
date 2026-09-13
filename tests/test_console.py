#!/usr/bin/env python3
########################################################################
#
# Project: Metalink Checker
# URL: http://www.nabber.org/projects/
# E-mail: webmaster@nabber.org
#
# Copyright: (C) 2007-2016, Neil McNab
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
# Filename: $URL$
# Last Updated: $Date$
# Version: $Rev$
# Author(s): Neil McNab
#
# Description:
#   Command line application that tests metalink clients.  Requires Python 2.5
# or newer.
#
# Instructions: uv run pytest
#
########################################################################

import hashlib
import os
import re
import tempfile

import pytest

from metalink import console

TESTS_FOLDER = os.path.dirname(__file__)


@pytest.fixture
def outdir():
    """Provide a temporary download directory that is cleaned up afterwards."""
    with tempfile.TemporaryDirectory(prefix="pymetalink-") as tmpdir:
        yield tmpdir


@pytest.fixture
def run_meta4(outdir, payload, http_server, ftp_server):
    """Run a ``.meta4`` fixture against the loopback test servers.

    The fixture files use ``HTTPPORT``/``FTPPORT`` placeholders which are
    replaced with the ports of the servers started for the test session.
    """

    def _run(filename, expect_failure=False):
        source = os.path.join(TESTS_FOLDER, filename)
        with open(source, encoding="utf-8") as handle:
            text = handle.read()

        text = text.replace("HTTPPORT", str(http_server.server_address[1]))
        text = text.replace("FTPPORT", str(ftp_server.socket.getsockname()[1]))

        meta4 = os.path.join(outdir, filename)
        with open(meta4, "w", encoding="utf-8") as handle:
            handle.write(text)

        old_wd = os.getcwd()
        retcode = -1
        try:
            os.chdir(outdir)
            retcode = console.run([meta4])
        finally:
            os.chdir(old_wd)

        if expect_failure:
            assert retcode != 0, "Expected a non-zero return code."
            return

        assert retcode == 0, "Expected return code of zero."
        for name in re.findall(r'<file name="([^"]+)"', text):
            path = os.path.join(outdir, name)
            assert os.access(path, os.F_OK), "File does not exist %s." % path
            assert os.stat(path).st_size == payload["size"], "Wrong file size."
            assert filehash(path, hashlib.sha1()) == payload["sha1"], (
                "Bad file checksum."
            )

    return _run


def test_1_create_subdir(run_meta4):
    run_meta4("1_create_subdir.meta4")


def test_1_empty_size(run_meta4):
    run_meta4("1_empty_size.meta4")


def test_1_fail_bad_directory_and_network_errors(run_meta4):
    run_meta4("1_fail_bad_directory_and_network_errors.meta4", expect_failure=True)


def test_1_http_redirect(run_meta4):
    run_meta4("1_http_redirect.meta4")


def test_1_metalink_one_file(run_meta4):
    run_meta4("1_metalink_one_file.meta4")


def test_1_metalink_three_files(run_meta4):
    run_meta4("1_metalink_three_files.meta4")


def test_1_no_checksums(run_meta4):
    run_meta4("1_no_checksums.meta4")


def test_1_only_ftp_and_http(run_meta4):
    run_meta4("1_only_ftp_and_http.meta4")


def test_2_fail_metalink_one_file_bad_main_md5(run_meta4):
    run_meta4("2_fail_metalink_one_file_bad_main_md5.meta4", expect_failure=True)


def test_2_only_ftp(run_meta4):
    run_meta4("2_only_ftp.meta4")


def test_2_only_http(run_meta4):
    run_meta4("2_only_http.meta4")


def test_3_fail_bad_only_advanced_checksums(run_meta4):
    run_meta4("3_fail_bad_only_advanced_checksums.meta4", expect_failure=True)


def test_3_metalink_bad_piece1and2(run_meta4):
    run_meta4("3_metalink_bad_piece1and2.meta4")


def test_3_metalink_bad_piece2(run_meta4):
    run_meta4("3_metalink_bad_piece2.meta4")


def test_3_only_advanced_checksums(run_meta4):
    run_meta4("3_only_advanced_checksums.meta4")


def filehash(thisfile, filesha):
    """
    First parameter, filename
    Returns SHA1 sum as a string of hex digits
    """
    try:
        filehandle = open(thisfile, "rb")
    except:
        return ""

    data = filehandle.read()
    while data != b"":
        filesha.update(data)
        data = filehandle.read()

    filehandle.close()
    return filesha.hexdigest()
