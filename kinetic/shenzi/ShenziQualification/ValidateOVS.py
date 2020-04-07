import os
import sys
import time
import signal
import subprocess
from argparse import ArgumentParser
SHENZI_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)).split('shenzi')[0],"shenzi")
sys.path.insert(0,SHENZI_PATH)
import OVS
from Mine.Config import StrFmt

class ValidateOVS:
    def __init__(self, serial_number):
        self.serial_number = serial_number
        self.success = True

    #Runs with the required parameters only
    def run_to_completion(self):
        subtests = [("Batches.py", "python Batches.py -s "+self.serial_number),
                    ("Deletes.py", "python Deletes.py -s "+self.serial_number),
                    ("MatrixTest.py", "python MatrixTest.py -s "+self.serial_number),
                    ("Simulation.py", "echo " + self.serial_number + " | python Simulation.py -o 4 -n 10 -l 5 ")]
        for script, cmd in subtests:
            print StrFmt.Notice("SUBTEST","run_to_completion", script, cmd.split(script)[1])
            p = subprocess.Popen(cmd.replace(script,os.path.join(SHENZI_PATH, "OVS", script)), shell=True)
            p.wait()
            if p.returncode != 0:
                self.success = False
                print StrFmt.Notice("Error", "script failed with status code "+str(p.returncode))

    def run_and_kill_with_sigint(self):
        subtests = [("Batches.py"),
                    ("Deletes.py")]
        for script in subtests:
            print StrFmt.Notice("SUBTEST","run_and_kill_with_sigint", script)
            cmd = "python "+os.path.join(SHENZI_PATH, "OVS", script)+" -r 10.0 -s "+self.serial_number
            p = subprocess.Popen("exec " + cmd, shell=True)
            time.sleep(60)
            os.kill(p.pid, signal.SIGINT)
            time.sleep(300) #Supposed max time for subprocess's clean exit
            p.wait()
            try:
                os.kill(p.pid, signal.SIGKILL)
                self.success = False
            except OSError as e:
                pass #If OSError was raised, that means PID didn't exist so earlier SIGINT was successful


    def run_with_all_parameters(self):
        subtests = [("Batches.py","python Batches.py -s " + self.serial_number+ " -i eth1 -k "+os.path.join(SHENZI_PATH, "Support", "Keys","FixedSequential")+" -c 2 -q 5 -r 30 --load_count=4 --first_put_force --key_no_prefix --report_max_lat --skip_version_check --flush_every_batch --random_seed=9"),
                    ("Deletes.py","python Deletes.py -s "+self.serial_number + " -i eth1 -l 10.0 -o 10000 -r 4.0"),
                    ("MatrixTest.py","python MatrixTest.py -s "+self.serial_number + " -i eth1 -t 8.0 -r 5.0 -c 1 4 -q 1 4 -qs 2 -cs 1 -k " + os.path.join(SHENZI_PATH, "Support", "Keys","FixedSequential") + " --load_count=4 --first_put_force --key_no_prefix --report_max_lat --skip_version_check --flush_every_batch --random_seed=9"),
                    ("Simulation.py","echo " + self.serial_number + " | python Simulation.py -o 4 -n 10 -l 5 --num_success=1 --full_lat")]
        for script, cmd in subtests:
            print StrFmt.Notice("SUBTEST","run_with_all_parameters", script, cmd.split(script)[1])
            p = subprocess.Popen(cmd.replace(script,os.path.join(SHENZI_PATH, "OVS", script)), shell=True)
            p.wait()
            if p.returncode != 0:
                self.success = False
                print StrFmt.Notice("Error", "script failed with status code "+str(p.returncode))

    def run_with_script_object(self):
        subtests = [(OVS.Batches, 20, 5),
                    (OVS.Deletes, 20, 2)]
        for script_obj, run_time, reporting_interval in subtests:
            print StrFmt.Notice("SUBTEST","run_with_script_object", script_obj.__name__)
            obj = script_obj(self.serial_number, reporting_interval=reporting_interval)
            obj.start()
            obj.wait(run_time)
            obj.stop()
            if obj.status != 0:
                self.success = False
                print StrFmt.Notice("ERROR", "script reported status code "+str(obj.status))

if __name__=="__main__":
    parser = ArgumentParser()
    parser.add_argument("-s", "--serial_number", type=str, required=True)
    args = parser.parse_args()

    vo = ValidateOVS(args.serial_number)
    vo.run_to_completion()
    vo.run_and_kill_with_sigint()
    vo.run_with_all_parameters()
    vo.run_with_script_object()
    if vo.success:
        sys.exit(0)
    else:
        sys.exit(1)
