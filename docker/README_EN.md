# n6 application on docker

Run the latest version of n6 with Docker and Docker Compose.
It will give you the ability to build and run system to collect, manage and distribute security information on a large scale. 

# Requirements
- Docker - the newest version
- Docker Compose - the newest version
- Clone this building environment

# Building environment
> Note: Make sure that You switched branch to n6 repository
 
`docker-compose build` -  build base images first. The result of the process are docker images.
> Note: The correct process of this command should finish with stdout code 0.
In case of errors please resolve errors first. Docker stack require all correct build images.

`docker-compose images` - return information about docker images. Should seen like below

```text
Container   Repository    Tag       Image Id      Size  
--------------------------------------------------------
mongo       n6_mongo     latest   183dd9153eff   374 MB 
mysql       n6_mysql     latest   a48e52e2029c   346 MB 
n6          n6_work      latest   08ead7e63e37   873 MB 
rabbit      n6_rabbit    latest   ee38f48eb709   171 MB 
web         n6_web       latest   178eb198844d   1.08 GB
```

- container `n6` - python environment with n6 app
- container `mongo` - database archive MongoDB
- container `mysql` - normalized database MariaDB
- container `rabbit` -  message broker
- container `web` - RestAPI, poral, admin panel

By default, the stack exposes the following ports:
- 80 - redirect to 443
- 443 - n6 Portal
- 4443 - n6 REST API
- 4444 - n6 Admin Panel
- 15671 - RabbitMQ

> Note: Make sure that all ports are not used by Your local computer.
> If port is using by other services, please change it in docker-compose.yml file.

# Running system
`docker-compose up` - starts all containers and shows n6 logs. 

You can also run all services in the background (detached mode) by adding the -d flag to the above command.
Give docker a few seconds to initialize.

# Work with docker environment
`docker-compose exec work bash` - bash interactive mode
`supervisorctl` - run components while container n6 starts

Running the n6 container initialize and start process implemented with supervisor.

Running components via supervisor works as demon process. Parsers are utilize for create RabbimMQ queues.

In interactive mode type in bash `n6+TAB` to presents all available components.
When application is running and need to know, how it works, launch one of the collectors.
Call one collector: `n6collector_abusechfeodotracker`
`curl --cert /root/certs/cert.pem --key /root/certs/key.pem -k 'https://web:4443/search/events.json?time.min=2015-01-01T00:00:00'` - will manual retrieve data in interactive mode 

**Checking availability services and watching system**

RabbitMQ - Internet browser. URL (`https://localhost:15671/`)
- Login: guest
- Password: guest

n6 Admin Panel: (`https://localhost:4444/org/`)

n6 portal: https://localhost/
- username: login@example.com
- organization: example.com
- password: aaaa

Checking RestAPI status (`https://localhost/api/info`)

Additional tools:

Robomongo - client GUI MongoDB
    
    Connection:
        - name: any ex. "n6-open"
        - address: localhost
        - port: 27017
    Autentication:
        - database: n6 or admin
        - username: admin
        - password: password
        - auth mechanism: MONGODB-CR

Interactive mode:

    `docker-compose exec mongo  bash`
    `mongo --host mongo n6 -u admin -p password`

Mysql - client GUI sql
   
    Mysql workbench:
        Connection name: any ex. "Local n6 instance"
        Connection method: Standard TCP/IP
        Hostname: localhost
        Port: 3306
        Username: root

Interactive mode:
    
    `docker-compose exec mysql  bash`
    `mysql --host mysql --user root -ppassword`        

# Shutdown and clean up
`docker-compose down --rmi all -v` -  stop and remove all containers, network bridge and docker images 
