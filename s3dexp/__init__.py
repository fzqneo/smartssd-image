# with open('/sys/devices/system/cpu/intel_pstate/no_turbo', 'r') as f:
#     assert 1==int(f.readline()), "Please run `make no-turbo` to turn off Turbo Boost."