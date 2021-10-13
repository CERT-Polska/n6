# Supervisor

Supervisor is a system for controlling processes' state under UNIX,
useful to manage the *n6* pipeline (`N6Core`) components.

```bash
(env)$ pip install supervisor
```

## Configuration

Create directories for Supervisor's config and log files. Create a configuration file in
`~/supervisor/supervisord.conf`. 
You can find example configuration in *n6* repository, in
`/home/dataman/n6/etc/supervisord/supervisord.conf`.

```bash
(env)$ mkdir -p ~/supervisord/{log,programs}
(env)$ cp ~/n6/etc/supervisord/supervisord.conf ~/supervisord
```

Generate config files for *n6* parsers and copy them to the `supervisord` directory:

```bash
(env)$ cd ~/n6/etc/supervisord/
(env)$ python get_parsers_conf.py
(env)$ cp programs/*.conf ~/supervisord/programs/
```

If you install *n6* in a different Virtualenv than recommended (i.e., other than `env`),
then you have to adjust a proper path in all of the files in `n6/etc/supervisord/programs` in
the `PATH` environment variable and in the `command` option:

```text
command=/home/dataman/<ENV_NAME>/bin/{program_command}
environment=PATH="/home/dataman/<ENV_NAME>/bin/"
```

## Running the Supervisor's process
To run the `supervisord` process:

```bash
(env)$ supervisord -c ~/supervisord/supervisord.conf
```

## Controlling the processes
You can manage processes managed by the `supervisord` with the `supervisorctl` command.

Inside the `supervisorctl` prompt type `status` to list all processes and their status:

```bash
supervisor> status
n6aggregator                            RUNNING   pid 3922, uptime 0:00:15
n6archiveraw                            RUNNING   pid 3942, uptime 0:00:15
n6comparator                            RUNNING   pid 3957, uptime 0:00:15
n6enrich:n6enrich_00                    STARTING  
n6filter                                RUNNING   pid 3927, uptime 0:00:15
n6parser_abusechfeodotracker            RUNNING   pid 3929, uptime 0:00:15
n6parser_abusechfeodotracker201908      RUNNING   pid 3951, uptime 0:00:15
n6parser_abusechpalevodoms              RUNNING   pid 3938, uptime 0:00:15
n6parser_abusechpalevodoms201406        RUNNING   pid 3937, uptime 0:00:15
n6parser_abusechpalevoips               RUNNING   pid 3948, uptime 0:00:15
n6parser_abusechpalevoips201406         RUNNING   pid 3943, uptime 0:00:15
n6parser_abusechransomwaretracker       RUNNING   pid 3934, uptime 0:00:15
n6parser_abusechspyeyedoms              RUNNING   pid 3946, uptime 0:00:15
n6parser_abusechspyeyedoms201406        RUNNING   pid 3928, uptime 0:00:15
n6parser_abusechspyeyeips               RUNNING   pid 3921, uptime 0:00:15
n6parser_abusechspyeyeips201406         RUNNING   pid 3950, uptime 0:00:15
n6parser_abusechsslblacklist            RUNNING   pid 3935, uptime 0:00:15
n6parser_abusechsslblacklist201902      RUNNING   pid 3923, uptime 0:00:15
n6parser_abusechsslblacklistdyre        RUNNING   pid 3925, uptime 0:00:15
n6parser_abusechurlhausurls             RUNNING   pid 3932, uptime 0:00:15
n6parser_abusechzeusdoms                RUNNING   pid 3947, uptime 0:00:15
n6parser_abusechzeusdoms201406          RUNNING   pid 3936, uptime 0:00:15
n6parser_abusechzeusips                 RUNNING   pid 3955, uptime 0:00:15
n6parser_abusechzeusips201406           RUNNING   pid 3940, uptime 0:00:15
n6parser_abusechzeustracker             RUNNING   pid 3949, uptime 0:00:15
n6parser_badipsserverexploitlist        RUNNING   pid 3953, uptime 0:00:15
n6parser_dnsbhmalwaredomainscom         RUNNING   pid 3945, uptime 0:00:15
n6parser_dnsbhmalwaredomainscom201412   RUNNING   pid 3941, uptime 0:00:15
n6parser_dnsbhmalwaredomainscom201906   RUNNING   pid 3931, uptime 0:00:15
n6parser_greensnow                      RUNNING   pid 3944, uptime 0:00:15
n6parser_misp                           RUNNING   pid 3939, uptime 0:00:15
n6parser_packetmailothers               RUNNING   pid 3924, uptime 0:00:15
n6parser_packetmailratware              RUNNING   pid 3933, uptime 0:00:15
n6parser_packetmailscanning             RUNNING   pid 3926, uptime 0:00:15
n6parser_spam404                        RUNNING   pid 3954, uptime 0:00:15
n6recorder                              RUNNING   pid 3930, uptime 0:00:15
```

You can use commands like `start` or `stop` to control a single or all of the processes.

## Managing message broker queues, created by running components
Check the RabbitMQ's management GUI for new queues, which should have been created by each
component that consumes incoming messages.

To start some data flow, you should run some collectors. You can do it manually, or schedule
Cron jobs to run them periodically.
