#!/usr/bin/python
"""
Difference
Usage: A.csv | ./dlDiff.py [-f B.csv] [-d descriptor]
       A : A CSV containing set A
       f : A CSV containing set B
       d : What descriptor to use as a primary key
Purpose: Prints out list A-B using A's header. If no set B is fed in then it
         will print A-A (nothing)
"""
import sys
from argparse import ArgumentParser

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------
if __name__=="__main__":
    # Input Arguments
    parser = ArgumentParser(usage='A.csv | ./dlDiff.py [-f="B.csv"] [-d="descriptor"]')
    parser.add_argument("-f", "--file", help="CSV of drives to filter out", default=None)
    parser.add_argument("-d", "--descriptor", help="What descriptor to use as a primary key",
                                                default="serial_number")
    args = parser.parse_args()

    # Check that there is data being piped in
    if sys.stdin.isatty():
        print parser.print_help()
        sys.exit(1)

    if args.file:
        # Get drive list B
        filter_drives = []
        with open(args.file) as file:
            header = [x.strip() for x in file.readline().split(",")]
            reference_index = header.index(args.descriptor)
            for line in file:
                values = [x.strip() for x in line.split(",")]
                filter_drives.append(values[reference_index])

        # Parse input stream
        header = [x.strip() for x in sys.stdin.readline().split(",")]
        header_index = header.index(args.descriptor)
        print ",".join(header)
        while True:
            line = sys.stdin.readline()
            if not line.strip():
                break
            line = [x.strip() for x in line.split(",")]
            if line[header_index] not in filter_drives:
                print ",".join(line)
