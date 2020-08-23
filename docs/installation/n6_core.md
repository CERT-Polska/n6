# Installation of *n6* packages

First, install `git` and change the shell user to `dataman`:

```bash
$ apt-get install git
$ su - dataman
```

Being logged in as `dataman`, clone the *n6* Git repository to `/home/dataman/n6`:

```bash
$ git clone https://github.com/CERT-Polska/n6.git n6
```

## *Virtualenv* initialization

Create and activate a new Python *virtualenv*, let us call it `env`; do not forget
to activate it:

```bash
$ virtualenv env
$ source env/bin/activate
```

## Running *setup* scripts of *n6* packages

For the typical installation of *n6* Python packages, run the `do_setup.py` script
in the cloned `n6` directory, with names of packages (names of parent directories of packages)
as its arguments:

```bash
(env)$ cd n6
(env)$ ./do_setup.py N6Lib N6Core N6SDK N6RestApi N6Portal N6AdminPanel
```

** You can add the `-a develop` argument to run the script in the *develop* mode. In this mode
a link file to each package is created in your `site-packages` directory. Then, every
change in code is reflected immediately, without having to install the affected package again. **

## Troubleshooting
### [ERROR] Failed to install the `mysql-python` Python package

There might be an issue with the `mysql-python` package during the setup of `N6Lib` package.

See more at [defectDojo issue 407](https://github.com/DefectDojo/django-DefectDojo/issues/407)

Quick command to resolve (as root):

```bash
$ sed '/st_mysql_options options;/a unsigned int reconnect;' /usr/include/mysql/mysql.h -i.bkp
```

After the successful installation, try the autocomplete option to reveal a list of *n6* components:

```bash
(env)$ n6  # <- try the TAB key directly after typing "n6" to see the results of autocompletion
```
