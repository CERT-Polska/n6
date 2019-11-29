For each public collector, during installation, there will be console command
generated in the form `n6collector_{trimmed_collector_class_name}` where the 
`trimmed collector class name` is lowercased collectors class name
with `collector` substring erased (for example: The `MyFirstCollector`
class would generate `n6collector_myfirst` command).

Each command calls the entrypoint function for the given collector.
Entrypoint functions must meet the following requirements:
* be in the same module as the collector they are referring to,
* have the identifier in the form `{collector_class_name}_main` where the
`collector_class_name` refers to the name of the collector class this function is
the entrypoint for,
* take no function arguments

If you do not want to implement the function by yourself, there is the helper
function which will generate entrypoint functions for you.

For the module you implement your collectors in, if they derive (indirectly or directly) from the
collectors base class (`AbstractBaseCollector`),
you can call `entry_point_factory` function from
the `n6.collectors.generic` module at the end of your module
to generate entry points for all collector classes the module contains.

Example call would look like this:
```python
entry_point_factory(sys.modules[__name__])
```

Generated entrypoint functions will create a collector instance with
the arguments taken from the `get_script_init_kwargs` and then
start the collector. They also take care of logging from the collector.

## Private collectors

It is important to note that the command will not be generated for the
collectors in the `generic` module as well as any collector class whose
name starts with the underscore character (for example
`_MyHiddenCollector`), as they are considered private and not for
external use. You yourself can implement private collectors if you need
so.