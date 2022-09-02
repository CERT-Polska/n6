# Collector Tests

Testing collectors can be tricky. Mostly because collectors work
asynchronously based on the `rabbitmq` as well as the fact that they
are treated as standalone programs.

Fortunately there are tools that take care of those things,
so we can focus only on writing our tests.

Those tools are located under the path `n6datasources.tests.collectors._collector_test_helpers`.
The most important one is `BaseCollectorTestCase` and here we will focus on it.

## Testing with BaseCollectorTestCase

The class goes nice with the `unittest_expander` package from pypi.
As _n6_ uses it for the unit testing we will use it as well.

### Test cases

First things first: we need some test cases.
We will obtain them using `foreach` and `paramseq` from `unittest_expander`.
We will also need `call` and `ANY` objects from the `mock` package.

```python
from unittest.mock import ANY, call

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase
from my_collectors import MyCollector


@expand
class TestMyCollector(BaseCollectorTestCase):

    COLLECTOR_CLASS = MyCollector

    @paramseq
    def cases():
        yield param(
            config_content="""
                [my_collector]
                XXXXXXXXXXX source_provider = friendly-org.domains
                url = https://www.example.com
            """,
            downloaded_jsons=[
                '{"tag": "example.com,some1,2019-10-11T23:59:59"}',
                '{"tag": "example.org,some2,2019-10-12T01:02:03"}',
            ],
            expected_output=[
                call(
                    'friendly-org.domains',
                    'example.com,some1,2019-10-11T23:59:59',
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'stream',
                        'headers': {},
                    },
                ),
                call(
                    'friendly-org.domains',
                    'example.org,some2,2019-10-12T01:02:03',
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'stream',
                        'headers': {},
                    },
                )
            ]
        )

    @foreach(cases)
    def test(self,
             config_content,
             downloaded_jsons,
             expected_output):
        pass  # perform one test case (TODO)
```

That is a lot of code for sure. So here is what we did here:

- set the `COLLECTOR_CLASS` class attribute to the tested class.
- created `cases` method which is a parameter sequence. For now, it only
  consists of one test case (the `param` object after `yield`). If we
  would like to add more test cases later all that would have to be done
  is to just yield other `param` objects.
- at last, we created the header of the `test` method which will perform a single test
  for each `param` object from `cases`.

So, after all of that, we need to implement the `test` method.

```python
    @foreach(cases)
    def test(self,
             config_content,
             downloaded_jsons,
             expected_output):
        collector = self._mocked_collector(config_content, downloaded_jsons)
        collector.run_handling()
        self.assertEqual(
            self.publish_output_mock.mock_calls,
            expected_output)

    def _mocked_collector(self, config_content, downloaded_jsons):
        self.patch_object(MyCollector,
                          '_download_data',
                          side_effect=downloaded_jsons)
        collector = self.prepare_collector(
            self.COLLECTOR_CLASS,
            config_content=config_content)
        return collector
```

And that's all. So what have we done? First, we created our collector
using the `prepare_collector` method, giving it a class of the
collector and the content of its (mocked) configuration. However, before
doing so, we mocked the `_download_data` method on the `MyCollector` class,
so that it will return the input data chunks we passed to the test. For
the purposes of this example we imply that the `MyCollector`'s method
`_download_data` is the one that deals just with downloading data from
an external data source and so we can mock it without disrupting the
collector's logic.

After receiving our collector in the `test` method,
we simply start it by calling `run_handling` on the collector.
Then we can make our assertion.
We compare the output we expected against the value
of the `mock_calls` property on the mocked output
queue. To put it in simple terms: `mock_calls` is just
the data expected to be inside the queue after the collector has
finished working.

We can see that the structure of the `test`
method corresponds to the 3A principle concerning writing
unit tests (Arrange, Act, Assert) - which is nice.
