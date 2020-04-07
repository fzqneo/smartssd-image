#!/usr/bin/python
"""
Sort
Usage: A.csv | ./dlSort.py 'attr_a', 'attr_b',..,'attr_n'
        A : A CSV containing set A
Purpose: It will sort the input in order of the attributes passed in.If no
         attributes are listed it will return A.
"""
import sys
import csv

SORT_LIST = []

def comparator(a, b):
    for i in SORT_LIST:
        if a[i] > b[i]:
            return 1
        if a[i] < b[i]:
            return -1
    return 0

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------
if __name__=="__main__":
    # If the help flag is given or no data is being piped in print usage and exit
    if '-h' in sys.argv or sys.stdin.isatty():
        print  'usage: A.csv | ./dlSort.py \'attr_a\', \'attr_b\',..,\'attr_n\''+\
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
        sort_order = []
        input_list = sys.argv[1:]
        for item in input_list:
            temp = item.split(",")
            for temp_item in temp:
                if temp_item:
                    sort_order.append(temp_item)

        # Parse A.csv
        input_data = []
        reader = csv.DictReader(sys.stdin)
        for row in reader:
            input_data.append(row)
        input_header = reader.fieldnames

        SORT_LIST = [i for i in sort_order if i in input_header]
        
        print ",".join(input_header)
        temp = sorted(input_data, cmp=comparator)
        for row in temp:
            print ",".join([row[i] for i in input_header])