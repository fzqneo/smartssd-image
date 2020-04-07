"""
Display Functions

This file has a collection of functions that can be used to
control how TestSuites display status on running subtests or
summaries once finished running.

Making your own Subtest Decorator:
    - Every subtest decorator contains the basic logic flow
      required to setup, run, and teardown a subtest. The
      developer can make a custom subtest decorator that
      displays whatever information they choose at any point
      in the logic flow that they choose.
    - The simplist way to create a new subtest is to copy the
      function titled "SubtestDecoratorNoDisplay", rename it
      what you would like and add print statements wherever
      you feel is best.

"""
from Subtest import Subtest

class color:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    ENDC = '\033[0m'

def SubtestDecoratorNoDisplay(subtest):
    def wrapper():
        try:
            subtest.setup()
            for kwargs in subtest.parameters:
                subtest.run(**kwargs)
            subtest.teardown()
        except (Subtest.SetupException, Subtest.TeardownException) as e:
            subtest.log_result(False, str(e))
    return wrapper

def SubtestDecorator0(subtest):
    def wrapper():
        try:
            print "[SETUP]"+str(subtest.__class__.__name__)+"|",
            subtest.setup()
            print "complete"
            for kwargs in subtest.parameters:
                formated_kwargs = ",".join(sorted([str(k)+':'+str(kwargs[k]) for k in kwargs]))
                print "[    ]"+str(subtest.__class__.__name__)+"|"+formated_kwargs+"\r",
                subtest.run(**kwargs)
                if subtest.results[-1].success:
                    print "["+color.GREEN+"PASS"+color.ENDC+"]"+str(subtest.__class__.__name__)+"|"+formated_kwargs
                else:
                    print "["+color.RED+"FAIL"+color.ENDC+"]"+str(subtest.__class__.__name__)+"|"+formated_kwargs
            print "[TEARDOWN]"+str(subtest.__class__.__name__)+"|",
            subtest.teardown()
            print "complete"
        except (Subtest.SetupException, Subtest.TeardownException) as e:
            print color.RED+str(e)+color.ENDC
            subtest.log_result(False, str(e))
    return wrapper

def SummaryReporter0(results):
    fails = {'subtest':[],
             'setup':[],
             'teardown':[]}
    testsuite_failed = False
    for result in results:
        if not result.success:
            testsuite_failed = True
            if 'Setup' in result.status_msg:
                fails['setup'].append(result)
            elif 'Teardown' in result.status_msg:
                fails['teardown'].append(result)
            else:
                fails['subtest'].append(result)
    if testsuite_failed:
        print color.RED+"Test Suite FAILED"+color.ENDC
        for category in fails:
            print "Failed "+category+" Count: "+str(len(fails[category]))
            for fail in sorted(fails[category]):
                if fail.run_kwargs is None:
                    print "\t"+fail.subtest_name+"|"+"-"+"|"+fail.status_msg
                else:
                    print "\t"+fail.subtest_name+"|"+",".join(sorted([str(k)+':'+str(fail.run_kwargs[k]) for k in fail.run_kwargs]))+"|"+fail.status_msg
    else:
        print color.GREEN+"Test Suite PASSED"+color.ENDC
