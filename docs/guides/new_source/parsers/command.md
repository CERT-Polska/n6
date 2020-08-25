# Parser Executable Commands

As with [collectors](../collectors/command.md) we can generate
a console command for our parser to be started with.

It works the same way as with collectors so it is
highly recommended to read their chapter about the matter
at hand.

The only difference would be that the function
`entry_point_factory` is now imported from the 
`n6.parsers.generic` module. Yet the usage stays
the same so it would look like so:

```python
from n6.parsers.generic import (
    BaseParser,
    entry_point_factory,
)

class MyParser(BaseParser):
    # parser implementation
    pass

entry_point_factory(sys.modules[__name__])
```
