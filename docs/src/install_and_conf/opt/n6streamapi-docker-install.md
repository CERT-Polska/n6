# Docker-Based Configuration of *n6 Stream API*

The *n6 Stream API* installation is based on Debian 12.
This guide describes how to install the [*n6 Stream Api*](../../usage/streamapi.md) in Docker.

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
To do this follow the official guide for [Docker-Based Installation](../../install_and_conf/docker.md).
If you already have **n6** a Docker based instance:

 * Make sure the Docker network `n6_n6-pub-net` is created.
 The Docker images of **n6** should be part of this network.

 * Do not forget to initialiaze  the `auth_db` database.

## Getting started

!!!Note
    Make sure you are in the top-level directory of the cloned source code repository.


To build the necessary images for **n6 Stream API**:
```bash
$ docker compose -f docker-compose.stream-api.yml build
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
$ docker compose -f docker-compose.stream-api.yml up
```



### Configuration of Stream API access 

First inside the `stream_api` container run the `n6anonymizer`:

```bash
$ docker compose exec stream_api bash
$ source venv-n6datapipeline/bin/activate
(venv-n6datapipeline)$ n6anonymizer
```


Then, in `n6adminpanel`, create a new Organization and a user within. Make sure the `Stream API Enabled` option is checked.

* Sync the org config with the stream api broker config:

Run the `exchange_updater` inside the `stream_api` container:

```bash
$ docker compose exec stream_api bash
$ source venv-n6datapipeline/bin/activate
(venv-n6datapipeline)$ python ~/n6/N6DataPipeline/n6datapipeline/aux/exchange_updater.py
```

### Testing

* Make sure the `n6anonymizer` is running within the `venv-n6datapipeline` environment in the `stream_api` container
* Connect to `stream_api_rabbit` on port `61614`, based on the Stream API [wiki](../../usage/streamapi.md)
* Push some data into the n6 pipeline. Ensure that the organization the user is connected to has all the necessary rights to read these events. The access list is the same as in the REST API and Portal
* Events should be received by the connected client
