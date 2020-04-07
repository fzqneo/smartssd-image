# Kinetic Python Client
The [kinetic-protocol](https://github.com/Seagate/kinetic-protocol) python client.

Requires:

* Python 2.7.x; Python 3.x is not supported
* pip program for python package management

---

## Installing Client from source

```
sudo ./install_client.sh
```

* If you already have a non-compatible version of python-protobuf installed, this command might fail. To resolve this, uninstall python-protobuf with the command below and try the install script again.

```
sudo pip uninstall protobuf
```

### Warning

If you have multiple client directories (e.g. path_A/python and path_B/python) and you ran install_client.sh from more than one of them, then you will have both packages installed at once. This can be very confusing to maintain/use and not all systems will chose the same client to use. Some systems will use the most recent install and some will use the first one installed. THIS IS NOT RECOMENDED. To undo this, simply remove (rm) all but one of the python client repos (whichever one you want to keep and use).

### Multi-user installs

*Advanced Users Only*

By default, the install script installs the pyhton client for all users on the system. If you would like to install the client for your user only, make the following changes to the install_client.sh script. This change also allows a user to use a different client than the system default (you can have the general system client and then the user-specified client).

```
sudo python setup.py develop            # Find the line that looks like this and
                                        # add the --user flag (as shown in the line
                                        # below)

sudo python setup.py develop --user     # The flag is --user, NOT --(your user name)
```

---

## Getting Started with the client
The examples directory contains several useful scripts for getting started.

```
import kv_client                            # Import kv_client library
c = kv_client.Client('localhost')           # Initialize client object
c.put('Hello','World', synchronization=1)   # Issue commands
c.wait_q(n)                                 # wait_q will return once there are
                                            # n or less outstanding commands
```

Responses are returned via specific callback methods. A user may specify their own callback methods. The callback has three parameters the response returned (message, command, and value). Examples of how to use callbacks can be found in examples/Callbacks.py

```
c.callback_delegate = "<user's method name>"
```

In order to use a secure (ssl) client you set use_ssl to true and assign the port to the tlsPort (likely 8443).

```
c = kv_client.Client('localhost', port=8443, use_ssl=True)
```