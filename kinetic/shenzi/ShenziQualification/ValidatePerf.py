import os
import sys
import subprocess
from argparse import ArgumentParser
SHENZI_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)).split('shenzi')[0],"shenzi")
sys.path.insert(0,SHENZI_PATH)
import Perf
from Mine.Config import StrFmt

class ValidatePerf:
    def __init__(self, serial_number):
        self.serial_number = serial_number
        self.success = True

    def run_basic(self):
        subtests = [(Perf.Puts, 120, 30),
                    (Perf.Gets, 30, 5),
                    (Perf.Deletes, 5, 2)]
        for script_obj, run_time, reporting_interval in subtests:
            print StrFmt.Notice("SUBTEST","run_basic", script_obj.__name__)
            obj = script_obj(self.serial_number, reporting_interval=reporting_interval)
            obj.start()
            obj.wait(run_time)
            obj.stop()
            if obj.status != 0:
                self.success = False
                print StrFmt.Notice("ERROR", "script reported status code "+str(obj.status))

    def run_to_completion(self):
        subtests = [("Puts.py"),
                    ("Gets.py"),
                    ("Deletes.py")]
        for script in subtests:
            print StrFmt.Notice("SUBTEST","run_to_completion", script)
            cmd = "python "+os.path.join(SHENZI_PATH, "Perf", script)+" -r 300 -s "+self.serial_number
            p = subprocess.Popen(cmd, shell=True)
            p.wait()
            if p.returncode != 0:
                self.success = False
                print StrFmt.Notice("Error", "script failed with status code "+str(p.returncode))

    def run_with_all_parameters(self):
        subtests = [("Puts.py", " -i eth1 -k "+os.path.join(SHENZI_PATH, "Support", "Keys","FixedSequential")+" -v 1000 -b 10 -o 100000 -r 10"),
                    ("Gets.py", " -i eth1 -k "+os.path.join(SHENZI_PATH, "Support", "Keys","FixedSequential")+" -o 100000 -r 10"),
                    ("Deletes.py", " -i eth1 -k "+os.path.join(SHENZI_PATH, "Support", "Keys","FixedSequential")+" -b 10 -o 100000 -r 10")]
        for script, args in subtests:
            print StrFmt.Notice("SUBTEST","run_with_all_parameters", script, args)
            cmd = "python "+os.path.join(SHENZI_PATH, "Perf", script)+args+" -s "+self.serial_number
            p = subprocess.Popen(cmd, shell=True)
            p.wait()
            if p.returncode != 0:
                self.success = False
                print StrFmt.Notice("Error", "script failed with status code "+str(p.returncode))

if __name__=="__main__":
    parser = ArgumentParser()
    parser.add_argument("-s", "--serial_number", type=str, required=True)
    args = parser.parse_args()

    vp = ValidatePerf(args.serial_number)
    vp.run_basic()
    vp.run_to_completion()
    vp.run_with_all_parameters()

    if vp.success:
        sys.exit(0)
    else:
        sys.exit(1)