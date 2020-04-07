#!/usr/bin/python
"""
Intersection
Usage: A.csv | ./dlIntersect.py [-f B.csv] [-d descriptor]
        A : A CSV containing set A
        f : A CSV containing set B
        d : What descriptor to use as a primary key
Purpose: Show me the drives common between lists A and B. If no set B
         is fed in then it will give A intersect A (which is just A)
"""
import sys
from argparse import ArgumentParser

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------
if __name__=="__main__":
    # Input Arguments
    parser = ArgumentParser(usage='A.csv | ./dlIntersect.py [-f="B.csv"] [-d="descriptor"]')
    parser.add_argument("-f", "--file", help="CSV of drives to filter out", default=None)
    parser.add_argument("-d", "--descriptor", help="What descriptor to use as a primary key", default="serial_number")
    args = parser.parse_args()

    # Check that there is data being piped in
    if sys.stdin.isatty():
        print parser.print_help()
        sys.exit(1)

    # If there was a B.csv
    if not args.file:
        while True:
            line = sys.stdin.readline().strip()
            if not line:
                break
            print line
    else:
        # Get drive list B
        header_B = []
        drives_B = []
        with open(args.file) as file:
            header_B = [x.strip() for x in file.readline().split(",")]
            reference_index = header_B.index(args.descriptor)
            for line in file:
                line = [x.strip() for x in line.split(",")]
                drives_B.append(line[reference_index])

        # Parse input stream
        drives = {}
        header_A = [x.strip() for x in sys.stdin.readline().split(",")]
        reference_index = header_A.index(args.descriptor)
        print ",".join(header_A)
        while True:
            input_line = sys.stdin.readline().strip()
            if not input_line:
                break
            input_line = [x.strip() for x in input_line.split(",")]
            if input_line[reference_index] in drives_B:
                temp = {}
                for index,item in enumerate(input_line):
                    temp[header_A[index]]=item
                drives[input_line[reference_index]]=temp

        # Print the results using header from A.csv
        for drive in drives:
            output_line = []
            for field in header_A:
                if field in drives[drive]:
                    output_line.append(drives[drive][field])
                else:
                    output_line.append('None')
            print ",".join(output_line)
