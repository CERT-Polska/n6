# Parser Tests

As with everything, _n6_ comes with a class simplifying the task at hand.
In this case, we'll have to look at the `ParserTestMixin` in the
`n6datasources.tests.parsers._parser_test_mixin` module.

We'll configure the test case by setting relevant
class attributes and then implement input and expected output
data as the method `cases`.

If you want to see all possible class attributes to set,
you should read the class definition itself.
We will focus only on the most important ones.

- `RECORD_DICT_CLASS` - the class of the mappings yielded by the
  parser's `parse` method. It defaults to `RecordDict` as most parsers
  use it. However, blacklist parsers use `BLRecordDict` so if the tested
  parser is the blacklist one be sure to set the attribute of your test
  case class to `BLRecordDict` (imported from `n6lib.record_dict`).
- `PARSER_CONSTANT_ITEMS` - same as `constant_items` in `BaseParser`.
- `PARSER_CLASS` - the class of the tested parser.
- `PARSER_BASE_CLASS` - the base class of the tested parser.
- `PARSER_SOURCE` - the source identifier in the `{source provider}.{source channel}`
  format (corresponds to the first two parts of parser's `default_binding_key`).
- `ASSERT_RESULTS_EQUAL` - the name of the test case method that will be used to test whether
  actual results are equal to the expected results. Defaults to `assertEqual` but can be changed,
  for example to `assertCountEqual` to not care about the order of the items
  inside collections.

Example test case could look like so:

```python
class TestMyParserSimpleCase(ParserTestMixin, unittest.TestCase)

    PARSER_SOURCE = 'source-provider.source-channel'
    PARSER_CLASS = MyParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'dos-victim',
    }
```

Then we can implement assertions by yielding pairs (2-tuples) of:
_input data_ and _expected output_.

```python
class TestMyParserSimpleCase(ParserTestMixin, unittest.TestCase)

    PARSER_SOURCE = 'source-provider.source-channel'
    PARSER_CLASS = MyParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'medium',
        'category': 'server-exploit',
    }

    def cases(self):
        yield (
            '{"tag": "example.com,some1.2019-10-11T23:59:59"}',
            [
                dict(
                    fqdn='example.com',
                    name='some1',
                    time='2019-10-11 23:59:59',
                ),
            ]
        )
        yield (
            '{"tag": "example.org,some2.2019-10-12T01:02:03"}',
            [
                dict(
                    fqdn='example.org',
                    name='some2',
                    time='2019-10-12 01:02:03',
                ),
            ]
        )
```

Of course, the input and resulting data fields will depend on the tested source.
`ParserTestMixin` automatically covers testing the `id` and `source`
fields as well as any fields that the `PARSER_CONSTANT_ITEMS` mapping
includes. We need to provide the values for any other fields in the
expected results.

It is also worth mentioning that the `ParserTestMixin` class also provides
a helper method for creating blacklist items, `get_bl_items`, which is
very useful when testing blacklist parsers.
