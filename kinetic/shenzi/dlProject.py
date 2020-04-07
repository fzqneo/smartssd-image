#!/usr/bin/python
"""
Project
Usage: A.csv | ./dlProject.py 'attr_a', 'attr_b',..,'attr_n'
        A : A CSV containing set A
Purpose: Given a combination of attributes it will display those attributes for all
         drives that have them in list A (I only want to see the serial numbers and
         firmware versions of list A). If no attributes are listed it will return A.
"""
import sys
import csv

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------
if __name__=="__main__":
    # If the help flag is given or no data is being piped in print usage and exit
    if '-h' in sys.argv or sys.stdin.isatty():
        print  'usage: A.csv | ./dlProject.py \'attr_a\', \'attr_b\',..,\'attr_n\''+\
                '\n\noptional arguments:\n  -h, --help'+\
                '            show this help message and exit'
        sys.exit(1)

    # If there were no attributes listed, print out input
    if len(sys.argv[1:]) < 1:
        while True:
            line = sys.stdin.readline().strip()
            if not line:
                break
            print line
    else:
        # Grab desired attribute list
        output_header = []
        input_list = sys.argv[1:]
        for item in input_list:
            temp = item.split(",")
            for temp_item in temp:
                if temp_item:
                    output_header.append(temp_item)

        # Parse A.csv
        print ",".join(output_header)
        reader = csv.DictReader(sys.stdin)
        for row in reader:
            line = []
            for field in output_header:
                try:
                    line.append(row[field])
                except KeyError:
                    line.append("")
            print ",".join(line)            
