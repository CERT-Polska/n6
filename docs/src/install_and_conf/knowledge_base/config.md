# Initialization and Configuration

## Necessary _n6_ packages

Make sure you have _n6_ system installed accordingly to the guides [Docker installation](../../install_and_conf/docker.md) or [Step-by-step installation](../../install_and_conf/step_by_step/index.md).

## _Knowledge Base_ runtime configuration

_Knowledge base_ is an optional functionality in the _n6_ system, switched off by default. If you want to use it, you must switch it on by setting the configuration option `knowledge_base.active` to `true` in the appropriate `*.ini` file.

```ini
knowledge_base.active = true
```

Switching on the _Knowledge base_ providing also in the ` GET /api/info` endpoint, after logging to the _n6_ system, a new field `knowledge_base_enabled` with the value set on `true` (the field is not seen after switching the _Knowledge base_ off).

_Knowledge base_ also needs for proper working the right filesystem structure, where articles are stored. Firstly you need to specify, in the appropriate `*.ini` file, the configuration option `knowledge_base.base_dir`, which specifies the path to the knowledge base directory.

```ini
knowledge_base.base_dir = ~/.n6_knowledge_base/
```

The next step is to create the output knowledge base directory using dedicated script `n6/N6Portal/n6portal/scripts/build_knowledge_base.sh`. The script creates in the specified in the `knowledge_base.base_dir` destination, the template of the knowledge base structure with samples of articles, groupped in examplary chapters.

```bash
(env_py3k)$ ./N6Portal/n6portal/scripts/build_knowledge_base.sh
```

At the end you need to reload the HTTP server (in our case Apache2):

```bash
$ sudo systemctl reload apache2
```

### Testing proper configuration

Properly initialized and configured _Knowledge Base_ should result in visible link to the Knowledge base in _n6 Portal_, in which should be shown examplary articles groupped in chapters.