if __name__ == "__main__":


    pipe_name = "/tmp/s3dexp-comm"
    server = Server(pipe_name)
    server.start()

    tic = time.time()
    i = 0
    while time.time() - tic < 10.:  # run for 10 sec
        # (Haithem): receive real request from 0MQ here. Should use poll.
        now = time.time()
        if now - tic > i:
            # generate a new request about every second, alternating between decode request and wait request
            if i % 2 == 0:
                path = next(path_gen)
                request = {'decode': i}
                print "Generating decode request {} {} @ {:.6f}".format(i, path, now)
                ss.sched_request(now, OP_DECODEONLY, request, on_complete, path)
            else:
                request = {'wait': i}
                print "Generating wait request {} @ {:.6f}".format(request, now)
                ss.sched_request(now, OP_DEBUG_WAIT, request, on_complete, None, wait=2)  # wait for 2 sec
            i += 1

        env.run(until=(time.time() + RUN_AHEAD))  # continuously keeps simulation up to real time

    # run till no events pending
    env.run()