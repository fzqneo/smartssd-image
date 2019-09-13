import socket

this_hostname = socket.gethostname()

try:
    with open('/sys/devices/system/cpu/intel_pstate/no_turbo', 'r') as f:
        assert 1==int(f.readline()), "Please run `make no-turbo` to turn off Turbo Boost."
except IOError:
    print "You are running on a Non-Linux platform, I guess. Don't bother with Turbo Boost."
    pass

