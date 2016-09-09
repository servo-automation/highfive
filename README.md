## Highfive

Highfive is a bot, which is meant to provide a welcoming environment for the newcomers, and also help the contributors by commenting, labeling or notifying them in issues and pull requests when an anticipated event occurs.

The stuff inside this repo (and all its sub-repos) is a rework of all the collaborative work done in the old [highfive](https://github.com/servo/highfive), with the limitations of the Github API in mind.

This repo is responsible for calling the various handlers with the payload "posted" by Github webhooks API. It basically runs the whole thing. It has the handlers (as submodules), the tests for them, and the other API-related stuff.

### Design

Calling `python runner.py` starts a Flask-based server, which listens to a particular port for `POST`ing of payloads. It can be tested lively at [Heroku platform](http://heroku.com/). Their free plan kills the server after a few minutes of inactivity, but once a payload is posted, the script will be executed and the payload will be handed over to the server. The initial startup delay isn't much, and hence it best suites our purpose.

All the payload handlers live inside `handlers`, grouped into submodules corresponding to each [webhook event](https://developer.github.com/webhooks/#events), so that we'll know which event triggers a handler, or in other words, which events have to be enabled while setting up a new webhook. Most often, we definitely don't wanna go for the "Send me everything" option that Github offers for a webhook, which thrashes your server with payloads related to every single event!

All the handlers have per-repo configuration. There's a `config.json` local to every handler, which determines how it should respond to an event. It has two basic keys. The `"active"` key tells whether the handler should be considered while processing an event-related payload. The `"repos"` key contains the per-repo config. Repository names are usually of the form `"owner/repo"`, but since it allows regex patterns, you can have dangerous matches like `"owner/*"` (which matches all the repos of an owner) and `"*"` (which matches any repo of any owner, i.e., every payload it gets).

There's a global [`config.json`](https://github.com/servo-highfive/highfive/blob/master/config.json) where we can enable/disable a group of handlers corresponding to an event. When multiple accounts and auth tokens are listed inside the global config, an user-token pair is chosen randomly just before handling a payload (so that the API requests are shared by multiple bots).

### Tests

The testsuite can be run offline with `python test.py`. **Every enabled handler should at least have one test!** (the testsuite enforces this rule). The tests are pretty simple. The test payloads live inside `tests` directory, which has the same structure as that of `handlers`.

Each test JSON has the `"initial"` and `"expected"` values, along with the actual `"payload"` (the one posted by Github). Once a handler is executed with a payload, the final values are asserted against the expected values. The `initial` and `expected` values can also be a list, so that we can test multiple cases with the same payload.

Github's payload JSONs are huge! They have a lot of useful information, but we won't be using most of them. In order to keep the test JSONs as precise as possible, there's a ["mark and sweep" cleaner](https://github.com/servo-highfive/highfive/blob/master/helpers/json_cleanup.py), which uses a wrapper type for finding those unused nodes. So, whenever we "get" a value corresponding to a key, the path is traced and marked. In the end, the unmarked values (or untraced paths) are thrown as errors by the testsuite. If you've added a new test, then the unused nodes can be cleaned up by running `python test.py write`.

`NodeMarker` is a *creepy* container. It wraps around all the objects! While most of the commonly used methods should work right now, in case you need to use a type-specific method (`lower` for `str`, for example), then you should add a new method to `NodeMarker`, asking it to access the method on the underlying type ([like so](https://github.com/servo-highfive/highfive/blob/8691a1ce0dce6045194f2a5510c0f63d2da72804/helpers/json_cleanup.py#L50-L51)). So, instead of working around in the main code, we're introducing workarounds in the cleaner. Well, everything comes at a cost!

### Supported handlers

#### [`issues`](https://developer.github.com/v3/activity/events/types/#issuesevent)
 - `label_notify`: Notify label watcher(s) in a comment when a label is added to an issue.
 - `label_response`: Comment when a label is added to an issue.

#### [`pull_request`](https://developer.github.com/v3/activity/events/types/#pullrequestevent)
 - `assign_people`: Assign people based on review requests in PR body or (pseudo-)random reviewer rotation.
 - `diff_check_warn`: Check the diff of the commits in a PR for added lines, changed files, or missing tests matching a pattern (specified in the config), and post a consolidated warning message on the match(es) found.
 - `path_watchers`: Notify watcher(s) in a comment whenever a PR makes changes to the "watched" paths.
 - `label_response`: Add/remove labels when a PR is opened/updated/closed.

---

### Installation (Heroku)

- Clone this repo.
- Create one (or more) Github account(s) for bot(s). Generate the corresponding auth tokens with the necessary [scopes](https://developer.github.com/v3/oauth/#scopes).<sup>[1]</sup>
- Update the global `config.json` with the account name(s) and auth token(s) and remove the events which you don't wanna handle. Update the `config.json` in the individual handlers appropriately.<sup>[2]</sup>
- Create an app at Heroku, `cd` into the repo's directory, and use the [toolbelt](https://devcenter.heroku.com/articles/heroku-command-line) to set the remote to your heroku app: <br /> `heroku git:remote -a <app-name>`
- Push to heroku!
- Go to the settings page of your repo, open "webhooks and services" and add a new webhook.
- The payload URL is your heroku app's `POST` URL, content type is `application/json`, choose "Let me select individual events", and select only those events you've enabled in the global config file.<sup>[3]</sup>
- In case you wanna verify that the payload sender is actually Github, generate a random key and put it in the "secret" box of your webhook. Then, update the global config with your secret key. When Github sends the payload, its [HMAC-SHA1 signature](https://developer.github.com/webhooks/securing/) will be verified by the script on execution.

**Note:** Ideally, you shouldn't share your auth tokens or the secret keys with anyone (not even heroku), but for the sake of making this thing to work, we don't have a choice. If you've got your own server, then there's nothing to worry about :)

<sup>
[1]: A bot should (at least) have the `repo` scope for the handlers to work.<br />
[2]: If you've removed an event from the global config file, then the entire group of handlers will be ignored. <br />
[3]: A clever strategy would be to have multiple apps, each taking care of a webhook event (or a set of handlers). <br />
</sup>
