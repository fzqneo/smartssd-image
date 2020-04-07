#!/usr/bin/python
"""
Union
Usage: A.csv | ./dlUnion.py [-f B.csv] [-d descriptor]
        A : A CSV containing set A
        f : A CSV containing set B
        d : What descriptor to use as a primary key
Purpose: Combine lists A and B using A's header, eliminate duplicates. If there
         are duplicates, the last item in A will persist. If no set B is fed in,
         it will return A union A (A without duplicates)
"""
import sys
from argparse import ArgumentParser
from Support.CSVTable import CSVTable
from Support.General import row_to_dict

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------
if __name__=="__main__":
    # Input Arguments
    parser = ArgumentParser(usage='A.csv | ./dlUnion.py [-f="B.csv"] [-d="descriptor"]')
    parser.add_argument("-f", "--file", help="CSV of drives to filter out", default=None)
    parser.add_argument("-d", "--descriptor", help="What descriptor to use as a primary key",
                                              default="serial_number")
    args = parser.parse_args()

    # Check that there is data being piped in
    if sys.stdin.isatty():
        print parser.print_help()
        sys.exit(1)

    # Set up
    DriveTable = CSVTable(args.descriptor)
    DriveTable.debug = False

    # Get drive list B
    if args.file:
        with open(args.file) as file:
            header_B = [x.strip() for x in file.readline().split(",")]
            for line in file:
                DriveTable.insert_data(row_to_dict(header_B,line))

    # Parse input stream
    header_A = [x.strip() for x in sys.stdin.readline().split(",")]
    while True:
        input_line = sys.stdin.readline().strip()
        if not input_line:
            break
        DriveTable.insert_data(row_to_dict(header_A, input_line))
    DriveTable.print_table(header_A)
