#!/usr/bin/env python
########################################################################
#
# Project: Metalink Checker
# URL: http://www.nabber.org/projects/
# E-mail: webmaster@nabber.org
#
# Copyright: (C) 2007-2016, Neil McNab
# License: GNU General Public License Version 2
#   (http://www.gnu.org/copyleft/gpl.html)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
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
# Instructions:
#   1. You need to have Python installed.
#   2. Run on the command line using: python tester.py
#   3. The program you are testing needs to return failure codes on exit.
#
########################################################################

import os
import hashlib
import sys
import optparse
import time
import subprocess
import shutil
import unittest
import ctypes
import signal

# Metalink Checker
CMD = "\"" + sys.executable + "\" ../console.py %s"
# Aria2
# CMD = "\"c:\\program files\\aria2\\aria2c.exe\" -M %s"

OUTDIR = os.getcwd()
TIMEOUT = 600
SUBDIR = "subdir"

IGNORE_TESTS = [] #["3_metalink-bad-piece1and2-without-torrent",
                #"3_metalink-bad-piece2-without-torrent"]

FILELIST = [
    {"filename": "curl-7.46.0.tar.bz2",
    "size": 3494481,
    "checksums": {"sha1": "96fbe5abe8ecfb923e4ab0a579b3d6be43ef0e96"}},
    {"filename": "curl-7.46.0.tar.bz2.1",
    "size": 3494481,
    "checksums": {"sha1": "96fbe5abe8ecfb923e4ab0a579b3d6be43ef0e96"}},
    {"filename": "curl-7.46.0.tar.bz2.2",
    "size": 3494481,
    "checksums": {"sha1": "96fbe5abe8ecfb923e4ab0a579b3d6be43ef0e96"}},
]

class TestMetalink(unittest.TestCase):
    
    def setUp(self):
        clean()

    def test_1_create_subdir(self):
        self.run_test("1_create_subdir.meta4")
    def test_1_empty_size(self):
        self.run_test("1_empty_size.meta4")
    def test_1_fail_bad_directory_and_network_errors(self):
        self.run_test("1_fail_bad_directory_and_network_errors.meta4")
    def test_1_http_redirect(self):
        self.run_test("1_http_redirect.meta4")
    def test_1_metalink_one_file(self):
        self.run_test("1_metalink_one_file.meta4")
    def test_1_metalink_three_files(self):
        self.run_test("1_metalink_three_files.meta4")
    def test_1_no_checksums(self):
        self.run_test("1_no_checksums.meta4")
    def test_1_only_ftp_and_http(self):
        self.run_test("1_only_ftp_and_http.meta4")
    def test_2_fail_metalink_one_file_bad_main_md5(self):
        self.run_test("2_fail_metalink_one_file_bad_main_md5.meta4")
    def test_2_only_ftp(self):
        self.run_test("2_only_ftp.meta4")
    def test_2_only_http(self):
        self.run_test("2_only_http.meta4")
    def test_3_fail_bad_only_advanced_checksums(self):
        self.run_test("3_fail_bad_only_advanced_checksums.meta4")
    def test_3_metalink_bad_piece1and2(self):
        self.run_test("3_metalink_bad_piece1and2.meta4")
    def test_3_metalink_bad_piece2(self):
        self.run_test("3_metalink_bad_piece2.meta4")
    def test_3_only_advanced_checksums(self):
        self.run_test("3_only_advanced_checksums.meta4")
    def test_4_empty_size_only_p2p(self):
        self.run_test("4_empty_size_only_p2p.meta4")
    def test_4_fail_metalink_bad_piece1and2_only_p2p(self):
        self.run_test("4_fail_metalink_bad_piece1and2_only_p2p.meta4")
    def test_4_fail_metalink_bad_piece2_only_p2p(self):
        self.run_test("4_fail_metalink_bad_piece2_only_p2p.meta4")
    def test_4_fail_metalink_one_file_bad_main_md5_only_p2p(self):
        self.run_test("4_fail_metalink_one_file_bad_main_md5_only_p2p.meta4")
    def test_4_no_checksums_only_p2p(self):
        self.run_test("4_no_checksums_only_p2p.meta4")
    def test_4_only_p2p(self):
        self.run_test("4_only_p2p.meta4")

    def run_test(self, filename):
        subdir = "."
        if filename.find("subdir") != -1:
            subdir = SUBDIR
            
        retcode = system(CMD % filename, TIMEOUT)

        if filename.find("fail") == -1:
            self.assertEqual(retcode, 0) # Expected return code of zero.
        else:
            self.assertNotEqual(retcode, 0) # Expected non zero return code.
            return True

        checklist = [0]
        if filename.find("three") != -1:
            checklist = [0,1,2]
        elif filename.startswith("4"):
            checklist = [3]
            
        for checkindex in checklist:
            temp = FILELIST[checkindex]
            tempname = os.path.join(OUTDIR, subdir, temp["filename"])
            assert os.access(tempname, os.F_OK), "File does not exist %s." % tempname
            self.assertEqual(os.stat(tempname).st_size, temp["size"]) # Wrong file size.
            self.assertEqual(filehash(tempname, hashlib.sha1()), temp["checksums"]["sha1"]) # Bad file checksum.

        return True


def suite(level = 3):
    suiteobj = unittest.TestSuite()

    filedir = "./"
    filenames = os.listdir(filedir)

    for filename in filenames:
        if filename.endswith(".meta4") and filename[:-6] not in IGNORE_TESTS:
            mysplit = filename.split("_", 1)
            myint = IsInt(mysplit[0])
            if myint and (int(mysplit[0]) <= int(level)):
                suiteobj.addTest(TestMetalink("test_" + filename[:-6]))
  
    return suiteobj


def clean():
    print "Running cleanup..."
    for fileitem in FILELIST:
        try:
            os.remove(os.path.join(OUTDIR, fileitem["filename"]))
        except: pass
        try:
            os.remove(os.path.join(OUTDIR, SUBDIR, fileitem["filename"]))
        except: pass
        shutil.rmtree(os.path.join(OUTDIR, SUBDIR), True)

def filehash(thisfile, filesha):
    '''
    First parameter, filename
    Returns SHA1 sum as a string of hex digits
    '''
    try:
        filehandle = open(thisfile, "rb")
    except:
        return ""

    data = filehandle.read()
    while(data != ""):
        filesha.update(data)
        data = filehandle.read()

    filehandle.close()
    return filesha.hexdigest()

def IsInt(str):
	""" Is the given string an integer?	"""
	ok = True
	try:
		num = int(str)
	except ValueError:
		ok = False
	return ok

def system(command, timeout=600, cwd=None):
    '''
    Alternative to os.system(), adds optional parameter to kill process
    after a given amount of time.
    First parameter, command to run on the local system
    Second parameter, optional, timeout command after this many seconds
    cwd string working directory or None
    Returns command exit code
    '''
    endtime = time.time() + timeout

    print command
    process = subprocess.Popen(command, shell=True, env=os.environ, cwd=cwd)
    while(True):
        time.sleep(1)
        #print "check:", process.poll()
        if process.poll() != None:
            return process.poll()
        if endtime <= time.time():
            # kill process here
            kill(process.pid)
            #print "Test timed out.  Process killed."
            raise AssertionError, "Test timed out.  Process killed."
            #return process.poll()
            
def kill(pid):
    if os.name == 'nt':
        return winkill(pid)
    return os.kill(pid, signal.SIGKILL)      
            
def winkill(pid):
    """kill function for Win32"""
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(1, 0, pid)
    return (0 != kernel32.TerminateProcess(handle, 0))            
        
def run():
    '''
    Start a console version of this application.
    '''
    global OUTDIR, CMD, TIMEOUT
    # Command line parser options.
    parser = optparse.OptionParser()
    parser.add_option("--level", "-l", dest="level", help="Set the level to test up to (default: 3)")
    parser.add_option("--command", "-c", dest="command", help="Command to run (use quotes as needed), %%s=metalink file")
    parser.add_option("--outdir", "-o", dest="outdir", help="Directory where the metalink client will output the downloaded files")
    parser.add_option("--timeout", "-t", dest="timeout", help="Sets the amount of time a test can run until it times out (default: 600 s)")
##    parser.add_option("--testcase", "-f", dest="testcase", help="Run a single test case")
    parser.add_option("--clean", dest="clean", action="store_true", help="Clear out any temporary files from testing")

    (options, args) = parser.parse_args()

    if options.outdir != None:
        OUTDIR = options.outdir
    if options.command != None:
        CMD = options.command
    if options.timeout != None:
        TIMEOUT = int(options.timeout)

    if options.clean != None:
        clean()
        return
    
    if len(args) != 0:
        suiteobj = unittest.TestSuite()
        for arg in args:
            suiteobj.addTest(TestMetalink(arg))
    else:
        if options.level != None:
            suiteobj = suite(options.level)
        else:
            suiteobj = suite(3)
    runner = unittest.TextTestRunner()
    results = runner.run(suiteobj)

    #print dir(suiteobj._tests)
    

if __name__=="__main__":
    run()
