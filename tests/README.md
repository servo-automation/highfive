### Tests

The testsuite can be run offline with `python tests`. Firstly, there are the unit tests which check the classes against a set of expectations. Then, there are the tests for the handlers themselves.

The handler tests are quite easy to write. The test payloads live inside `handler_tests` directory, which has the same structure as that of `event_handlers` (i.e., individual handler directories under the corresponding events).  Every test JSON has `"initial"` and `"expected"` values, along with the actual `"payload"` (which is a brief concise version of Github's webhook paylods).

The initial values are used for initializing the handlers. Then, the payload is passed to the handler. After handling the payload, the final values are asserted against the expected values. The `initial` and `expected` values can also be a list, so that we can test multiple cases with the same payload.

Github's payload JSONs are huge! They have a lot of useful information, but we won't be using most of them. In order to keep the test JSONs as precise as possible, there's a ["mark and sweep" cleaner](./handler_tests/json_cleaner.py), which uses a wrapper (`NodeMarker`) over the nodes in the payload dictionary. Whenever we "get" a value corresponding to a key, the path is traced and marked. In the end, the unmarked values (or untraced paths) are thrown as errors by the testsuite. If you've added a new test, then the unused nodes can be cleaned up by running `CLEAN=1 python tests` (which overwrites the dirty JSONs).

`NodeMarker` is a *creepy* container. It wraps around all the objects! While most of the commonly used methods should work right now, in case you need to use a type-specific method (`lower` for `str`, for example), then you should add a new method to `NodeMarker`, asking it to access the method on the underlying type ([like so](https://github.com/servo-automation/highfive/blob/cf15962a88b77aae90289edaebfe647f1538b274/tests/handler_tests/json_cleaner.py#L37-L38)). So, instead of working around in the main code, we're introducing workarounds in the cleaner. Well, everything comes at a cost!
