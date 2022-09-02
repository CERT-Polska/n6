**Note:** `N6Core` contains legacy _Python-2-only_ stuff.

When it comes to the basic _n6_ pipeline components, please use the new,
_Python-3-only_ stuff residing in `N6DataPipeline`.

When it comes to the data-sources-related components -- i.e., collectors
and parsers -- `N6DataSources` is the place where any new stuff is to be
implemented (in Python 3). The collectors and parsers residing in
`N6Core` will be gradually migrated to `N6DataSources` (for those data
sources than are not obsolete).
