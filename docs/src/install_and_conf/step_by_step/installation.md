<style>
  code.language-bash::before{
    content: "$ ";
  }
</style>


# Installing *n6* Components

## Where Are We?

Before any operations, ensure the current working directory is the home
directory of `dataman` (which is supposed to be the user in whose shell
you execute all commands):

```bash
cd ~
```


## New *Virtual Environment*

Create a new Python *virtual environment*... Let its name, for the
purposes of this guide, be `env_py3k`:

```bash
python3.11 -m venv env_py3k
```

Then, activate it:

```bash
source ./env_py3k/bin/activate
```

Now you can run the Python interpreter...

```bash
python
```

...to check if everything is OK:

```python
>>> import sys
>>> sys.version_info[:2]
(3, 11)
>>> sys.executable
'/home/dataman/env_py3k/bin/python'
>>> exit()  # Do not forget to exit Python :)
```


## Actual Installation

Enter the *n6* source code directory:

```bash
cd n6
```

...and execute the following command to install all *n6* components:

```bash
./do_setup.py -u all
```

!!! info

    The suggested command-line option `-u` causes that, before any other
    action, the basic package installation tools (*pip* and *uv*) will be
    automatically upgraded to their newest versions.

!!! tip

    The `do_setup.py` script offers a bunch of other command-line options.

    In particular, you can add the `--dev` (or `-d`) option to install *n6*
    in the *development* mode:

    ```
    ./do_setup.py -u --dev all
    ```

    ...so that, after installation of *n6* packages, every change to their
    source code in subdirectories of `/home/dataman/n6/*` will be reflected
    in the *virtual environment* -- without the necessity to install the
    affected packages again. Apart from that, `--dev` ensures that certain
    useful test and development tools (e.g., `pytest`) are also installed.

    To learn more about `do_setup.py`'s command-line arguments, execute:

    ```
    ./do_setup.py --help
    ```

After successful installation, use the shell autocomplete mechanism to
reveal all available executable scripts provided by the installed *n6*
components:

```bash
n6  # <- try the TAB key directly after typing "n6" to use autocompletion
```


## What did we just install?

The positional command-line argument `all` passed to `./do_setup.py`
made the script install *all* components of *n6*, that is:

* **_n6 pipeline_ components** -- whose implementation can be found in
  these `n6/`'s subdirectories:
    * `N6DataSources` -- providing all basic *collectors* and *parsers* (i.e.,
      the `n6collector_*` and `n6parser_*` components, focused on dealing
      with particular *data sources*)
    * `N6DataPipeline` -- providing such components as: `n6enrich`,
      `n6aggregator`, `n6comparator`, `n6filter`, `n6recorder` and
      others...

* **_web_ components of _n6_** -- whose implementation can be found in
  these `n6/`'s subdirectories:
    * `N6Portal` -- providing **_n6 Portal_** (the GUI for end users)
    * `N6RestApi` -- providing **_[n6 REST API](../../usage/restapi.md)_**
      (for those end users who prefer to interact with *n6* via custom
      client scripts/applications...)
    * `N6AdminPanel` -- providing **_n6 Admin Panel_** (a simple GUI app
      for administrators only -- to manage the contents of *Auth DB*)
    * *not discussed in this guide:* `N6BrokerAuthApi` (providing a [RabbitMQ
      HTTP auth backend](https://github.com/rabbitmq/rabbitmq-server/blob/v3.13.x/deps/rabbitmq_auth_backend_http/README.md)
      implementation, being a part of the optional **_[n6 Stream
      API](../../usage/streamapi.md)_** stuff -- see a separate [setup
      guide dedicated to *n6 Stream API*...](../opt/streamapi/docker.md))

* *n6*'s library stuff and helper scripts -- whose implementation can be
  found in the `n6/`'s subdirectories `N6Lib` and `N6SDK`.

!!! note ""

    **See also:**

    *[Architecture and Data Flow Overview](../../data_flow_overview.md)*
