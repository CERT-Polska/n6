# Parser Executable Commands

As with [collectors](../collectors/command.md) we can generate
a console command for our parser to be started with.

It works the same way as with collectors, so it is
highly recommended to read their chapter about the matter
at hand.

The only difference would be that the function
`add_parser_entry_point_functions` is now imported from the
`n6datasources.parsers.base` module. Yet the usage stays
the same, so it would look like so:

```python
from n6datasources.parsers.base import (
    BaseParser,
    add_parser_entry_point_functions,
)

class MyParser(BaseParser):
    # parser implementation
    pass

add_parser_entry_point_functions(sys.modules[__name__])
```
