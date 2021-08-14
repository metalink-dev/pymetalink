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
# Instructions: poetry run pytest
#
########################################################################

import os
import hashlib
import time
import shutil
import pytest

from metalink import console

OUTDIR = "/tmp"
TIMEOUT = 600
SUBDIR = "subdir"

TESTS_FOLDER = os.path.dirname(__file__)


FILELIST = [
    {
        "filename": "curl-7.46.0.tar.bz2",
        "size": 3494481,
        "checksums": {"sha1": "96fbe5abe8ecfb923e4ab0a579b3d6be43ef0e96"},
    },
    {
        "filename": "curl-7.46.0.tar.bz2.1",
        "size": 3494481,
        "checksums": {"sha1": "96fbe5abe8ecfb923e4ab0a579b3d6be43ef0e96"},
    },
    {
        "filename": "curl-7.46.0.tar.bz2.2",
        "size": 3494481,
        "checksums": {"sha1": "96fbe5abe8ecfb923e4ab0a579b3d6be43ef0e96"},
    },
]


def test_1_create_subdir():
    run_test("1_create_subdir.meta4")


def test_1_empty_size():
    run_test("1_empty_size.meta4")


def test_1_fail_bad_directory_and_network_errors():
    run_test("1_fail_bad_directory_and_network_errors.meta4")


def test_1_http_redirect():
    run_test("1_http_redirect.meta4")


def test_1_metalink_one_file():
    run_test("1_metalink_one_file.meta4")


def test_1_metalink_three_files():
    run_test("1_metalink_three_files.meta4")


def test_1_no_checksums():
    run_test("1_no_checksums.meta4")


def test_1_only_ftp_and_http():
    run_test("1_only_ftp_and_http.meta4")


def test_2_fail_metalink_one_file_bad_main_md5():
    run_test("2_fail_metalink_one_file_bad_main_md5.meta4")


def test_2_only_ftp():
    run_test("2_only_ftp.meta4")


def test_2_only_http():
    run_test("2_only_http.meta4")


def test_3_fail_bad_only_advanced_checksums():
    run_test("3_fail_bad_only_advanced_checksums.meta4")


def test_3_metalink_bad_piece1and2():
    run_test("3_metalink_bad_piece1and2.meta4")


def test_3_metalink_bad_piece2():
    run_test("3_metalink_bad_piece2.meta4")


def test_3_only_advanced_checksums():
    run_test("3_only_advanced_checksums.meta4")


def test_4_empty_size_only_p2p():
    run_test("4_empty_size_only_p2p.meta4")


def test_4_fail_metalink_bad_piece1and2_only_p2p():
    run_test("4_fail_metalink_bad_piece1and2_only_p2p.meta4")


def test_4_fail_metalink_bad_piece2_only_p2p():
    run_test("4_fail_metalink_bad_piece2_only_p2p.meta4")


def test_4_fail_metalink_one_file_bad_main_md5_only_p2p():
    run_test("4_fail_metalink_one_file_bad_main_md5_only_p2p.meta4")


def test_4_no_checksums_only_p2p():
    run_test("4_no_checksums_only_p2p.meta4")


def test_4_only_p2p():
    run_test("4_only_p2p.meta4")


def run_test(filename):
    subdir = "."
    if filename.find("subdir") != -1:
        subdir = SUBDIR

    old_wd = os.getcwd()
    retcode = -1
    try:
        os.chdir(OUTDIR)
        retcode = console.run([os.path.join(TESTS_FOLDER, filename)])
    finally:
        os.chdir(old_wd)

    if filename.find("fail") == -1:
        assert retcode == 0, "Expected return code of zero."
    else:
        assert retcode != 0, "Expected non zero return code."
        return True

    checklist = [0]
    if filename.find("three") != -1:
        checklist = [0, 1, 2]
    elif filename.startswith("4"):
        checklist = [3]

    for checkindex in checklist:
        temp = FILELIST[checkindex]
        tempname = os.path.join(OUTDIR, subdir, temp["filename"])
        assert os.access(tempname, os.F_OK), "File does not exist %s." % tempname
        assert os.stat(tempname).st_size == temp["size"], "Wrong file size."
        assert (
            filehash(tempname, hashlib.sha1()) == temp["checksums"]["sha1"]
        ), "Bad file checksum."

    return True


@pytest.fixture(autouse=True, scope="session")
def clean():
    print("Running cleanup...")
    for fileitem in FILELIST:
        try:
            os.remove(os.path.join(OUTDIR, fileitem["filename"]))
        except:
            pass
        try:
            os.remove(os.path.join(OUTDIR, SUBDIR, fileitem["filename"]))
        except:
            pass
        shutil.rmtree(os.path.join(OUTDIR, SUBDIR), True)


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
