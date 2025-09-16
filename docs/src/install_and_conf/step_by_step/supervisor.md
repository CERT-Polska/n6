<style>
  code.language-bash::before{
    content: "$ ";
  }
</style>


# Managing *n6 Pipeline* Components with *Supervisor*

[*Supervisor*](https://supervisord.org/) is a tool for controlling
processes' state under UNIX-like systems (such as Linux-based ones).

This turns out to be very useful for managing *n6 pipeline* components.


## Where Are We?

Again, before any operations, ensure the current working directory is
the home directory of `dataman` (which is supposed to be the user in
whose shell you execute all commands):

```bash
cd ~
```

Also, make sure the Python *virtual environment* [in
which](installation.md#new-virtual-environment) *n6* has been
[installed](installation.md#actual-installation) is active:

```bash
source ./env_py3k/bin/activate
```


## Configuration

First, install *Supervisor*:

```bash
pip install supervisor
```

Then, create directories for Supervisor's configuration and log files.

```bash
mkdir -p supervisord/{log,programs}
```

Now, create a configuration file in `~/supervisor/supervisord.conf`,
basing it on the example configuration from the *n6* source code
repository:

```bash
cp n6/etc/supervisord/supervisord.conf supervisord
```

Finally, generate configuration files for *parser* components of *n6*,
and copy them to the `supervisord` directory:

```bash
cd n6/etc/supervisord
```

```bash
PYTHONPATH=/home/dataman/n6/N6DataSources python get_parsers_conf.py \
  && cp programs/*.conf ~/supervisord/programs
```

```bash
cd ~
```

!!! note

    If you installed *n6* in a different *virtual environment* than
    recommended (i.e., other than `env_py3k`), you have to adjust paths
    in all files in `supervisord/programs`:

    ```
    command=/home/dataman/<ENV_NAME>/bin/{program_command}
    ```

    ```
    environment=PATH="/home/dataman/<ENV_NAME>/bin/"
    ```


## Running the Supervisor's Process

Open **a separate `dataman`'s shell session** and activate our *Virtual
Environment*:

```bash
source ./env_py3k/bin/activate
```

Then run the `supervisord` daemon process...

```bash
supervisord -c ~/supervisord/supervisord.conf
```


## Controlling the Supervisor's Processes

Execute:

```bash
supervisorctl -c ~/supervisord/supervisord.conf
```

Inside the `supervisorctl` prompt, type `status` to list all processes
and their statuses:

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

You can use commands like `start` or `stop` to control a single process
or all processes...

!!! tip

    Inside the `supervisorctl` prompt, type `help` to learn more about
    available commands...


## Components and Queues...

Check the RabbitMQ's management web interface for new queues, which
should have been created by each *n6 pipeline* component that is
supposed to consume incoming messages.

To start data flow, you need to run some *collectors*. You can do it
manually, or schedule *Cron* jobs to run them periodically...

!!! note

    From each *collector*, data is received by a *parser* (in rare cases,
    by multiple *parsers*).
