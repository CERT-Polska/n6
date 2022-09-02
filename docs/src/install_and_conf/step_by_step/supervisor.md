# Supervisor

!!!note

    The following examples assume the home directory path is `/home/dataman`
    and the project directory path is `/home/dataman/n6`.

Supervisor is a system for controlling processes' state under UNIX,
useful to manage the _n6_ pipeline (`N6DataPipeline`) components and (`N6DataSources`) sources.

```bash
(env)$ pip install supervisor
```

## Configuration

Create directories for Supervisor's config and log files. Create a configuration file in
`~/supervisor/supervisord.conf`.
You can find example configuration in _n6_ repository, in
`/home/dataman/n6/etc/supervisord/supervisord.conf`.

```bash
(env)$ mkdir -p ~/supervisord/{log,programs}
(env)$ cp ~/n6/etc/supervisord/supervisord.conf ~/supervisord
```

Generate config files for _n6_ parsers and copy them to the `supervisord` directory:

```bash
(env)$ cd ~/n6/etc/supervisord/
(env)$ python get_parsers_conf.py
(env)$ cp programs/*.conf ~/supervisord/programs
```

If you install _n6_ in a different Virtualenv than recommended (i.e., other than `env`),
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
n6parser_abusechfeodotracker202110.conf RUNNING   pid 3929, uptime 0:00:15
n6recorder                              RUNNING   pid 3930, uptime 0:00:15
```

You can use commands like `start` or `stop` to control a single or all of the processes.

## Managing message broker queues, created by running components

Check the RabbitMQ's management GUI for new queues, which should have been created by each
component that consumes incoming messages.

To start some data flow, you should run some collectors. You can do it manually, or schedule
Cron jobs to run them periodically.
