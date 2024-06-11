#!/usr/bin/env python
#
# Copyright: (C) 2016, Neil McNab
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

import os
import sys

import metalink.download as download


def run(args):
    for item in args:
        progress = ProgressBar()
        result = download.get(
            item,
            os.getcwd(),
            handlers={
                "status": progress.download_update,
                "bitrate": progress.set_bitrate,
                "time": progress.set_time,
            },
            segmented=True,
        )
        progress.download_end()
        if not result:
            return -1
    return 0


class ProgressBar:
    def __init__(self, length=79):
        self.length = length
        self.bitrate = None
        self.time = None
        self.show_bitrate = True
        self.show_time = True
        self.show_bytes = True
        self.show_percent = True
        # print ""
        # self.update(0, 0)
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
            bytes = f" {current_bytes:.2f}/{total_bytes:.2f} MB"

        bitinfo = ""
        if self.bitrate is not None and self.show_bitrate:
            if self.bitrate > 1000:
                bitinfo = " %.2f Mbps" % (float(self.bitrate) / float(1000))
            else:
                bitinfo = " %.0f kbps" % self.bitrate

        timeinfo = ""
        if self.time is not None and self.time != "" and self.show_time:
            timeinfo += " " + self.time

        length = (
            self.length
            - 2
            - len(percenttxt)
            - len(bytes)
            - len(bitinfo)
            - len(timeinfo)
        )

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
        if os.name != "nt":
            sys.stdout.write("\n")

    def end(self):
        self.update(1, 1)
        print("")

    def download_end(self):
        self.download_update(1, self.total_size, self.total_size)
        print("")


def main():
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
