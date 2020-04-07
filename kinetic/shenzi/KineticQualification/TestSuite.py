"""
Test Suite

A user can create a TestSuite and populate it with subtests then run
it on a specified drive. TestSuites allow the user to control the
order in which the subtests are run, and what information is displayed
during a subtest run and at completion of the test suite.
"""
import random
from threading import Thread, Event
from DisplayFunctions import SubtestDecorator0, SummaryReporter0

class TestSuite(object):
    def __init__(self, name):
        self._inactive = Event()
        self._inactive.set()
        self._halt_subtest_iter = Event()

        self.name = name
        self._subtest_decorator = SubtestDecorator0
        self._summary_reporter = SummaryReporter0
        self._subtests = {'to_run':[], 'complete':[]}
        self._run_order = []
        self._run_thread = Thread(target=self._run, name='TestSuite-'+self.name+' run thread')

    def _suite_must_be_inactive(method):
        """
        A decorator that will only ever call the method if the
        test suite is not running

        Returns:
            False: The test suite is active and the method was not called
            True:  The test suite is inactive and the method was called
        """
        def wrapper(self, *args, **kwargs):
            if self._inactive.isSet():
                method(self, *args, **kwargs)
                return True
            else:
                return False
        return wrapper

    def _run(self, serial_number, interface):
        """
        Start will kick off a thread to run this method that then runs
        through all the subtests and prints a summary after

        Args:
            serial_number: Serial number of the drive you'd like to run
            interface: Interface on the drive that you'd like to speak to
        """
        for index in self._run_order:
            if self._halt_subtest_iter.isSet():
                break
            elif self._subtests['to_run'][index] is None:
                continue
            else:
                subtest_instance = self._subtests['to_run'][index](serial_number, interface)
                self._subtest_decorator(subtest_instance)()
                self._subtests['complete'].append((index, subtest_instance))
                self._subtests['to_run'][index] = None
        self._inactive.set()

    def start(self, serial_number, interface=None, resume=True):
        """
        Initializes the test suite to run and then kicks off the run thread

        Args:
            serial_number: Serial number of the drive you'd like to run
            interface: Interface on the drive that you'd like to speak to
            resume: If true, the suite will continue running subtests where it left off
                    if false, the suite will wipe out all current results and start the run from
                    the begining

        Returns:
            None: Everything was started correctly
            (str): There was an error initializing or running and it did not start,
                   check string for error information
        """
        if not self._inactive.isSet():
            return "TestSuite is already running"
        self._inactive.clear()
        self._halt_subtest_iter.clear()
        self._run_thread = Thread(target=self._run,
                                   args=(serial_number, interface),
                                   name='TestSuite-'+self.name+' run thread')
        if not resume:
            for index, subtest in self._subtests['complete']:
                self._subtests['to_run'][index] = subtest.__class__
            self._subtests['complete'] = []
        self._run_thread.start()

    def wait(self, timeout=31556926):
        """
        Will return once the suite is inactive

        Args:
            timeout: max amount of time to wait before returning, default
                     is one year so that the wait can be interrupted

        Returns:
            True: the suite ended on its own
            False: the wait timed out
        """
        return self._inactive.wait(timeout=timeout)

    def stop(self):
        """
        Signals the suite to stop running and then returns once
        it is inactive
        """
        self._halt_subtest_iter.set()
        self.wait()

    @_suite_must_be_inactive
    def report_summary(self):
        """
        If there is a summary reporter specified, it will compile a list
        of all the current subtest results objects and feed them to the summary
        reporter
        """
        if self._summary_reporter is not None:
            results = []
            for index, subtest in self._subtests['complete']:
                results += subtest.results
            self._summary_reporter(results)

    @_suite_must_be_inactive
    def set_subtest_decorator(self, deco):
        self._subtest_decorator = deco

    @_suite_must_be_inactive
    def set_summary_reporter(self, reporter):
        self._summary_reporter = reporter

    @_suite_must_be_inactive
    def add_subtest(self, subtest):
        self._run_order.append(len(self._subtests['to_run']))
        self._subtests['to_run'].append(subtest)

    @_suite_must_be_inactive
    def specify_run_order(self, use_original=False, random_seed=None):
        """
        Allows the user to set the order back to its original and/or randomize it

        Args:
            use_original: if True, it will set the run order back to the original
                          order before checking the random seed argument
            random_seed: if None, there is no randomization of order
                         otherwise, uses the random seed to shuffle the run order
        """
        if use_original:
            self._run_order = range(len(self._subtests['to_run']))
        if random_seed is not None:
            random.Random(random_seed).shuffle(self._run_order)