#!/usr/bin/env python

import sys
import os

import metalink.download as download


def run():
    for item in sys.argv[1:]:
            progress = ProgressBar()
            result = download.get(item, os.getcwd(), handlers={"status": progress.download_update, "bitrate": progress.set_bitrate, "time": progress.set_time}, segmented = True)
            progress.download_end()
            if not result:
                sys.exit(-1)

class ProgressBar:
    def __init__(self, length = 79):
        self.length = length
        self.bitrate = None
        self.time = None
        self.show_bitrate = True
        self.show_time = True
        self.show_bytes = True
        self.show_percent = True
        #print ""
        #self.update(0, 0)
        self.total_size = 0

    def download_update(self, block_count, block_size, total_size):
        self.total_size = total_size
        
        current_bytes = float(block_count * block_size) / 1024 / 1024
        total_bytes = float(total_size) / 1024 / 1024
            
        try:
            percent = 100 * current_bytes / total_bytes
        except ZeroDivisionError:
            percent = 0
            
        if percent > 100:
            percent = 100

        if total_bytes < 0:
            return


        percenttxt = ""
        if self.show_percent:
            percenttxt = " %.0f%%" % percent

        bytes = ""
        if self.show_bytes:
            bytes = " %.2f/%.2f MB" % (current_bytes, total_bytes)
            
        bitinfo = ""
        if self.bitrate != None and self.show_bitrate:
            if self.bitrate > 1000:
                bitinfo = " %.2f Mbps" % (float(self.bitrate) / float(1000))
            else:
                bitinfo = " %.0f kbps" % self.bitrate

        timeinfo = ""
        if self.time != None and self.time != "" and self.show_time:
            timeinfo += " " + self.time
                
        length = self.length - 2 - len(percenttxt) - len(bytes) - len(bitinfo) - len(timeinfo)

        size = int(percent * length / 100)            
        bar = ("#" * size) + ("-" * (length - size))
        output = "[%s]" % bar
        output += percenttxt + bytes + bitinfo + timeinfo
        
        self.line_reset()
        sys.stdout.write(output)

    def set_bitrate(self, bitrate):
        self.bitrate = bitrate
        
    def set_time(self, time):
        self.time = time

    def update(self, count, total):
        if count > total:
            count = total
            
        try:
            percent = 100 * float(count) / total
        except ZeroDivisionError:
            percent = 0

        if total < 0:
            return

        percenttxt = ""
        if self.show_percent:
            percenttxt = " %.0f%%" % percent

        length = self.length - 2 - len(percenttxt)

        size = int(percent * length / 100)
        bar = ("#" * size) + ("-" * (length - size))
        output = "[%s]" % bar
        output += percenttxt
        
        self.line_reset()
        sys.stdout.write(output)

    def line_reset(self):
        
        sys.stdout.write("\b" * 80)
        if os.name != 'nt':
            sys.stdout.write("\n")
        
    def end(self):
        self.update(1, 1)
        print("")

    def download_end(self):
        self.download_update(1, self.total_size, self.total_size)
        print("")


if __name__ == "__main__":
    run()

