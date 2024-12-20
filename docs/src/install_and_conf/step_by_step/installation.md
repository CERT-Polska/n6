The following examples assume the home directory is `/home/dataman` 
and the project path is `/home/dataman/n6`.

# Installation of _n6_ Components

## Shell user

First, change the shell user to `dataman`:

```bash
$ su - dataman
```

## Installing specific python version

If you already have Python 3.9 installed skip this step.

Download Python:
```bash
$ wget https://www.python.org/ftp/python/3.9.2/Python-3.9.2.tgz
```

Once the download is complete, extract the gzipped archive:
```bash
$ tar -xf Python-3.9.2.tgz
```
Create makefiles
```bash
$ cd Python-3.9.2
$ ./configure --enable-optimizations
```
Start build process
```bash
$ make -j $(nproc)
```

Run install script as root (use altinstall to not overwrite the default system python3 binary) 
```bash
$ make altinstall
```

Check if Python was installed properlly
```bash
$ python3.9 --version
```


## _Virtualenv_ initialization

Create and activate a new Python _virtualenv_, let us call it `env_py3k`; 

If you installed Python 3.9 use:
```bash
$ virtualenv --python="/usr/local/bin/python3.9" /home/dataman/env_py3k
$ source /home/dataman/env_py3k/bin/activate
```

Otherwise:
```bash
$ virtualenv /home/dataman/env_py3k
$ source /home/dataman/env_py3k/bin/activate
```

Check the python version being used:

```bash
$ python --version
Python 3.9.**
```

## Running setup scripts of _n6_ packages

For the typical installation of _n6_ Python packages, run the `do_setup.py` script
in the cloned `n6` directory, with names of packages (names of parent directories of packages)
as its arguments:

```bash
(env_py3k)$ cd /home/dataman/n6
(env_py3k)$ pip install setuptools==68.1.0
(env_py3k)$ ./do_setup.py N6Lib N6SDK N6DataPipeline N6DataSources N6RestApi N6Portal N6AdminPanel N6BrokerAuthApi;
```

!!! note

    You can add the `-a develop` argument to run the script in the *develop*
    mode. In this mode a link file to each package is created in your
    `site-packages` directory. Then, every change in code is reflected
    immediately, without having to install the affected package again.

After successful installation, try the autocomplete option to reveal a list of _n6_ components:

```bash
(env_py3k)$ n6  # <- try the TAB key directly after typing "n6" to see the results of autocompletion
```
