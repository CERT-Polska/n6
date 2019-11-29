# State

Some collectors need to preserve their state between consecutive runs.
The usual case is that we want to remember some information which allows
us to identify the data we have already downloaded as to not download it again
and make a mess out of our database with redundant data.

The most important thing to note here is that each collector is used as
a OS process. So it can be run to download some data, then end its life;
then it is supposed to be run again -- by some scheduler, like e.g. cron -- after a few hours
to check if some new data have been added to the source.
So now we know that we cannot store our state in the process memory
as it will be deallocated when the process ends. And so we need
some kind of persistent storage.

## Implementation

`N6Core`'s module `n6.collectors.generic` comes with a class mix-in `CollectorWithStateMixin` (not to be
confised with the deprecated legacy ones: `CollectorStateMixIn` and
`CollectorStateMixInPlus`!) which saves the state as a pickle (so it
can be almost any Python object) inside the *n6*'s cache directory.

`CollectorWithStateMixin` consist of 4 methods and an `__init__`.
We will care only about 3 of them

* `save_state(self, state)` - saves the given state as a pickle in the cache directory.
* `load_state(self)` - tries to load and returns a previously saved state from the cache directory.
  If it failed it calls `make_default_state` (see below) to obtain the default state.
* `make_default_state(self)` - creates the default state object of the collector.
The default implementation just returns `None`. 

This class is a mix-in so it does not modify the `run_handling` method of
a collector in any way whatsoever. So it is your responsibility to call
`load_state` before starting collecting data and `save_state` just before
the exiting (or after each state update, this method ensures that in case
of the collector's crash we will recover at point right before the error has occurred).

Note that `CollectorWithStateMixin` does some initialization in `__init__`
which is later used by the `load_state` and `save_state` methods.
So make sure to call it (typically just using the `super()` technique).

### What does __init__ do?

You can skip this part and just jump to the example but if you are
curious the here.

`__init__` basically just sets the path of the state file by joining 
`cache_dir` path with the generated state's file name.

How does the object know the cache's directory path? From the
`config` attribute under the `cache_dir` key. So make sure it
is specified in the configuration. 


## Example

```python
class MyStatefullCollector(CollectorWithStateMixin, BaseCollector):

    type = 'stream' 

    config_spec = '''
        [my_statefull_collector]
        source :: str
        cache_dir :: str
    '''

    def make_default_state(self):
        return {}
    
    def run(self):
        self.state = self.load_state()
        super(MyStatefullCollector, self).run()  # <- main activity of collector
        self.save_state(self.state)

    def start_publishing(self):
        output_rk, output_data_body, output_prop_kwargs = self.get_output_components()
        self.publish_output(output_rk, output_data_body, output_prop_kwargs)
        self.inner_stop()        

    def get_source_channel(self, **processed_data):
        return 'example-channel'

    def get_output_data_body(self, **kwargs): 
        data = self._collect_data(self._url) 
        return data
    
    def _collect_data(self, url):
        data = self._download(only_newer_than=self.state.get('last_utc'))
        self.state['last_utc'] = data.time_utc
        return data

    def _download(self, only_newer_than):
        # download some data newer than the `only_newer_than` time
``` 

In the example above the state is a simple dictionary (note that an
empty dictionary is returned by the above implementation of
`make_default_state`). Here we load the state in an extended version of
the `QueuedBase`'s method `run`.

In the `_collect_data` (called in `get_output_data_body` which is
called in `start_publishing`) we update our state with the just
downloaded data. In this case it is just the creation time of the
processed chunk so we will not try to download older bits of data.

In case of this collector, only when the communication with RabbitMQ
has been properly closed we save our state (see again our extended
version of the `run` method).


## Remarks

Some base classes (but *not* `BaseCollector`) already implement state management be themselves;
in those cases you do not need to derive from `CollectorWithStateMixin`.
Instead read their documentation.
