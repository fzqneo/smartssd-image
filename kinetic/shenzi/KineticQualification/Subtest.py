"""
Subtest

Subtest is a parent class that lays the foundation for all KineticQual
subtests created. The subtest interface is designed to work with the
TestSuite class so all subtests can be run as a part of a TestSuite.
"""
class Subtest(object):
    parameters = [{}]

    class Result(object):
        def __init__(self, subtest_name, run_kwargs, success, status_msg):
            self.subtest_name = subtest_name
            self.run_kwargs = run_kwargs
            self.success = success
            self.status_msg = status_msg

    class SetupException(Exception):
        def __init__(self, message):
            Exception.__init__(self, "SetupException:"+str(message)+".")

    class TeardownException(Exception):
        def __init__(self, message):
            Exception.__init__(self, "TeardownException:"+str(message)+".")

    def __init__(self, serial_number, interface):
        self.parameters = self.__class__.parameters
        self.results = []
        self.serial_number = serial_number
        self.interface = interface

    def setup(self):
        pass

    def run(self, **kwargs):
        """
        run must always call log_result once (and only once) before returning.
        """
        pass

    def teardown(self):
        pass

    def log_result(self, success, status_msg, run_kwargs=None):
        self.results.append(Subtest.Result(subtest_name=self.__class__.__name__,
                                           run_kwargs=run_kwargs,
                                           success=success,
                                           status_msg=str(status_msg)))
