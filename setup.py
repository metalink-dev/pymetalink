# -*- coding: utf-8 -*-

from distutils.core import setup
import sys
import os.path
import shutil
#import glob
import zipfile

APP_NAME = 'pymetalink'
VERSION = '6.1'
LICENSE = 'GNU GPL'
DESC = 'A metalink library for Python.'
AUTHOR_NAME = 'Neil McNab'
EMAIL = 'nabber00@gmail.com'
URL = 'http://www.metalinker.org'


def clean():
    ignore = []
    
    filelist = []
#    filelist.extend(glob.glob("*metalink*.txt"))
    filelist.extend(rec_search(".zip"))
    filelist.extend(rec_search(".pyc"))
    filelist.extend(rec_search(".pyo"))

    
    try:
        shutil.rmtree("build")
    except: pass
    try:
        shutil.rmtree("dist")
    except: pass
#    try:
#        shutil.rmtree("buildMetalink")
#    except: pass
#    try:
#        shutil.rmtree("buildmetalinkw")
#    except: pass
    
#    try:
#        shutil.rmtree("tests_temp")
#    except: pass
    
    for filename in filelist:
        if filename not in ignore:
            try:
                os.remove(filename)
            except: pass

def create_zip(rootpath, zipname, mode="w"):
    print zipname
    myzip = zipfile.ZipFile(zipname, mode, zipfile.ZIP_DEFLATED)
    for root, dirs, files in os.walk(rootpath):
        for filename in files:
            filepath = os.path.join(root, filename)
            filehandle = open(filepath, "rb")
            filepath = filepath[len(rootpath):]
            text = filehandle.read()
            #print filepath, len(text)
            myzip.writestr(filepath, text)
            filehandle.close()
    myzip.close()

            
def rec_search(end, abspath = True):
    start = os.path.dirname(__file__)
    mylist = []
    for root, dirs, files in os.walk(start):
        for filename in files:
            if filename.endswith(end):
                if abspath:
                    mylist.append(os.path.join(root, filename))
                else:
                    mylist.append(os.path.join(root[len(start):], filename))
                    
    return mylist

if sys.argv[1] == 'clean':
    clean()
else:
    setup(
	  packages = ['metalink'],
      #data_files = data,
      name = APP_NAME,
      version = VERSION,
      license = LICENSE,
      description = DESC,
      author = AUTHOR_NAME,
      author_email = EMAIL,
      url = URL
      )