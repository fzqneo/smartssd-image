from s3dexp.sim.client import Client
from google.protobuf.json_format import MessageToJson

if __name__ == "__main__":

    pipe_name = "/tmp/s3dexp-comm"
    client = Client(pipe_name)
    client.connect()
    response = client.decode_only("foo")
    print "Received response %s" % MessageToJson(response)

    response = client.debug_wait(10)
    print "Received response %s" % MessageToJson(response)
