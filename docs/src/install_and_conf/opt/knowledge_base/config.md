<style>
  code.language-bash::before{
    content: "$ ";
  }
</style>


# Initialization and Configuration

## Necessary _n6_ packages

Make sure you have _n6_ system installed accordingly to the guides [Docker-Based Installation](../../../install_and_conf/docker.md) or [Step-by-Step Installation](../../../install_and_conf/step_by_step/index.md).

## _Knowledge Base_ runtime configuration

*Knowledge Base* is an optional functionality in the _n6_ system, switched off by default. If you want to use it, you must switch it on by setting the configuration option `knowledge_base.active` to `true` in the appropriate `*.ini` file.

```ini
knowledge_base.active = true
```

!!! info

    If the *Knowledge Base* feature is active and a Portal user is logged in,
    responses from the Portal API's endpoint `GET /api/info` include one extra
    field: `knowledge_base_enabled` (with the value `true`).

To use the feature, you need a filesystem structure where your *Knowledge Base* articles will be stored.

First, you need to specify, in the appropriate `*.ini` file, the configuration option
`knowledge_base.base_dir`, setting it to the path to the knowledge base directory:

```ini
knowledge_base.base_dir = ~/.n6_knowledge_base/
```

The next step is to create the structure. You can do that by running
the `n6/N6Portal/n6portal/scripts/build_knowledge_base.sh` script. It
creates (in the specified `knowledge_base.base_dir` destination) the
initial *Knowledge base* structure (already containing a few useful
articles, grouped in a couple of chapters).

```bash
cd n6 && ./N6Portal/n6portal/scripts/build_knowledge_base.sh
```

Finally, you need to reload the HTTP server:

```bash
sudo service apache2 restart
```

### Testing proper configuration

Properly initialized and configured *Knowledge Base* should result in a
visible `Knowledge Base` link in the *n6 Portal*'s GUI (to the left of
the *user menu* icon in the upper right corner).
