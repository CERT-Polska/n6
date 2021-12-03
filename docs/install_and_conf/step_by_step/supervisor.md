# Supervisor

Supervisor is a system for controlling processes' state under UNIX,
useful to manage the *n6* pipeline (`N6DataPipeline`) components and (`N6DataSources`) sources.

```bash
(env_py3k)$ pip install supervisor
```

## Configuration

Create directories for Supervisor's config and log files. Create a configuration file in
`~/supervisor/supervisord.conf`. 
You can find example configuration in *n6* repository, in
`/home/dataman/n6/etc/supervisord/supervisord.conf`.

```bash
(env_py3k)$ mkdir -p ~/supervisord/{log,programs}
(env_py3k)$ cp ~/n6/etc/supervisord/supervisord.conf ~/supervisord
```

or for Python 2 `N6Core` components:

```bash
(env)$ mkdir -p ~/supervisord/{log,programs_py2k}
(env)$ cp ~/n6/etc/supervisord/supervisord_py2k.conf ~/supervisord
```

Generate config files for *n6* parsers and copy them to the `supervisord` directory:

```bash
(env_py3k)$ cd ~/n6/etc/supervisord/
(env_py3k)$ python get_parsers_conf.py
(env_py3k)$ cp programs/*.conf ~/supervisord/programs
```

If you want to use configuration files for Python 2:

```bash
(env)$ cd ~/n6/etc/supervisord/
(env)$ python get_parsers_conf_py2k.py
(env)$ cp programs/*.conf ~/supervisord/programs_py2k
```

If you install *n6* in a different Virtualenv than recommended (i.e., other than `env_py3k`),
then you have to adjust a proper path in all of the files in `n6/etc/supervisord/programs` in
the `PATH` environment variable and in the `command` option:

```text
command=/home/dataman/<ENV_NAME>/bin/{program_command}
environment=PATH="/home/dataman/<ENV_NAME>/bin/"
```

## Running the Supervisor's process
To run the `supervisord` process:

```bash
(env_py3k)$ supervisord -c ~/supervisord/supervisord.conf
```

If you want to run the `supervisord` process for components in Python 2:
```bash
(env_py3k)$ supervisord -c ~/supervisord/supervisord_py2k.conf
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
