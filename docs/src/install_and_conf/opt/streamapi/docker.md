# *n6 Stream API*: Docker-Based Installation

The *n6 Stream API* installation is based on Debian 12.
This guide describes how to set up an instance of [*n6 Stream Api*](../../../usage/streamapi.md) with Docker.

The simplified data flow of the `n6 Stream API`:

```
                      n6's internal pipeline
                              |
                          event data
                              ↓
                        n6anonymizer
                              |
                  event data per client organization
                              ↓
                    Stream API Server (RabbitMQ)

------------------------------------------------------------------------------

                            Client
                              |
                      initial STOMP communication
                              ↓
                    Stream API Server ←→ Broker Auth API + Auth DB 
                              |        (authenticaion & authorization)
                              |
                    event data per client organization
                              ↓
                            Client
```

## Prerequisites

To build the Docker version of the **n6 Stream API**,  we first need to set up the Docker version of **n6**.
To do this follow the official guide for [Docker-based *n6* installation](../../docker.md).
Once you have a Docker-based instance of **n6**:

* Make sure the Docker network `n6_n6-pub-net` is created.
  The Docker images of **n6** should be part of that network.

* Make sure the *Auth DB* database has been initialized.

## Getting started

!!!Note
    Make sure you are in the top-level directory of the cloned source code repository.


To build the necessary images for **n6 Stream API**:
```bash
docker compose -f docker-compose.stream-api.yml build
```

If the build process was successful, you should be able to run the following command to obtain a result similar to what is listed here:

```bash
docker images | grep n6
```

```bash
n6_stream_api          latest    c6da117e027b   3 hours ago     1.17GB
n6_worker              latest    834b41858684   3 hours ago     2.29GB
n6_web                 latest    ede14648e4c0   3 hours ago     3.15GB
n6_base                latest    f8a048d63db2   3 hours ago     1.93GB
n6_mysql               latest    2f5da49187d5   3 hours ago     434MB
n6_stream_api_rabbit   latest    0f8faa554d36   3 hours ago     253MB
n6_rabbit              latest    ad5b4cf53d4e   3 hours ago     253MB
n6_mailhog             latest    55b5f0a82c69   3 years ago     392MB
```



To launch the Docker version of **n6 Stream API** run.
```bash
docker compose -f docker-compose.stream-api.yml up
```



### Configuration of Stream API access 

First inside the `stream_api` container run the `n6anonymizer`:

```bash
docker compose exec stream_api bash
source venv-n6datapipeline/bin/activate
n6anonymizer
```

!!!Note
    The `Anonymizer` will not generate any output unless specific error handling or logging mechanisms are configured.

Then, in `n6adminpanel`, create a new Organization and a user within. Make sure the `Stream API Enabled` option is checked.

* Sync the org config with the stream api broker config:

Run the `exchange_updater` inside the `stream_api` container:

```bash
docker compose exec stream_api bash
source venv-n6datapipeline/bin/activate
python /home/dataman/n6/N6DataPipeline/n6datapipeline/aux/exchange_updater.py
```

### Testing

* Make sure the `n6anonymizer` is running within the `venv-n6datapipeline` environment in the `stream_api` container
* Make sure you have created the *n6* user's API Key (see the relevant fragment of the [Docker-based *n6* installation guide](../../docker.md#setting-api-key))
* Connect to `stream_api_rabbit` on port `61614` (see the [Stream API usage guide](../../../usage/streamapi.md) or use the script provided below)
* Push some data into the n6 pipeline. Ensure that the organization the user is connected to has all the necessary rights to read these events. The access list is the same as in the REST API and Portal
* Events should be received by the connected client


#### Example client (stomp.py required)

To use the provided script fill the required variables: `STREAM_API_RABBIT_DOCKER_IP`, `login`, `passcode`.
```
import ssl
import stomp   # type: ignore
import time

STREAM_API_RABBIT_DOCKER_IP = ''
PORT = 61614
login = <USER_LOGIN>
passcode = <USER_API_KEY>

conn = stomp.Connection([(STREAM_API_RABBIT_DOCKER_IP, PORT)], heartbeats=(3000, 3000))
conn.set_ssl(for_hosts=[(STREAM_API_RABBIT_DOCKER_IP, PORT)], ssl_version=ssl.PROTOCOL_TLS)

class MyListener(stomp.ConnectionListener):

	def on_connecting(self, host_and_port):
		print(f"Connecting to {host_and_port}")

	def on_connected(self, frame):
		print("********* CONNECTED ************")
		return super().on_connected(frame)

	def on_error(self, frame):
		print("Error:\n%s" % frame)

	def on_message(self, frame):
		print("Message received:\n%s" % frame)

	def on_disconnected(self):
		print("\n****** DISCONNECTED *****")
		# return super().on_disconnected()


conn.set_listener('', MyListener())
conn.connect(login=login, passcode=passcode, wait=True)

conn.subscribe(destination="/exchange/<YOUR_ORGANIZATION>.com/*.*.*.*", id="001", ack="auto")

try:
	while True:
		time.sleep(1)
except KeyboardInterrupt:
	print("Interrupted")
	conn.disconnect()

```
Example output:
```
Message received:
{cmd=MESSAGE,headers=[{'subscription': '001', 'destination': '/exchange/clients/threats.phish.hidden.123456789abcdef0', 'message-id': 'T_001@@session-N-jGLLK57hJFJgk6KKHF7j@@11','redelivered': 'false', 'n6-client-id': 'example.com', 'persistent': '1', 'content-length': '291'}],body={"category": "phish", "time": "2025-05-20T16:32:37Z", "fqdn": "example1.com", "restriction": "public", "address": [{"ip": "1.1.1.1"}, {"ip": "2.2.2.2"}], "source": "hidden.123456789abcdef0", "id": "a6f8765c4a9e8d874cb64876a373bc65", "confidence": "high", "type": "event"}}
```