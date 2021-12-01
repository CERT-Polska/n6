# Installation of _n6_ components

First, install `git` and change the shell user to `dataman`:

```bash
$ apt-get install git
$ su - dataman
```

## Obtaining the source code

Being logged in as `dataman`, with this user's home directory as the
current working directory, clone the _n6_ Git repository (to
`/home/dataman/n6`):

```bash
$ git clone https://github.com/CERT-Polska/n6.git n6
```

## _Virtualenv_ initialization

Create and activate a new Python _virtualenv_, let us call it `env`; do not forget
to activate it:

```bash
$ virtualenv env
$ source env/bin/activate
```

## Running _setup_ scripts of _n6_ packages

For the typical installation of _n6_ Python packages, run the `do_setup.py` script
in the cloned `n6` directory, with names of packages (names of parent directories of packages)
as its arguments:

```bash
(env)$ cd n6
(env)$ ./do_setup.py N6Core N6RestApi N6Portal N6AdminPanel
```

> **Note:** You can add the `-a develop` argument to run the script in the _develop_ mode. In this mode a link file to each package is created in your `site-packages` directory. Then, every change in code is reflected immediately, without having to install the affected package again.

After successful installation, try the autocomplete option to reveal a list of _n6_ components:

```bash
(env)$ n6  # <- try the TAB key directly after typing "n6" to see the results of autocompletion
```
