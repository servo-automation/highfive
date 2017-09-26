## Highfive

Highfive is a Github integration (bot), meant to provide a welcoming environment for the newcomers to open source, and also help the contributors by commenting, labeling or notifying them in issues and pull requests when an anticipated event occurs. This is a rewrite of all the collaborative work done in the old [highfive](https://github.com/servo/highfive), with the limitations of Github API in mind.

### Running

Calling `python cgi-bin/serve.py` starts a Flask server, which listens to a particular port for `POST`ing of payloads. It can be tested lively at [Heroku platform](https://heroku.com/) (see below for installation). Their free plan kills the server after a few minutes of inactivity, but once a payload is posted, the script will be executed and the payload will be handed over to the server. So, it works for us.

Or, if you love CGI, then `cgi-bin/post.py` will be your `POST` endpoint. Make sure that your server forwards all HTTP headers to the script (most of the servers do, FYI). In the latter case, you need to setup a cron job and poke the script like `SYNC=1 cgi-bin/post.py` every few hours or something (since there are some state-maintaining handlers which have scheduled actions). In case of the Flask server, this polling will be done automatically by a separate daemon thread.

### Structure

All handlers live inside `handlers`, grouped into directories corresponding to each [webhook event](https://developer.github.com/webhooks/#events), so that we'll know which event triggers a handler, or in other words, which events have to be enabled while setting up a new integration. We definitely don't wanna check all the permissions offered by Github, as it thrashes your server with payloads from every single event!

Highfive has another group of handlers called "sync" handlers, which store their state information in a database. All payloads (regardless of their event) are piped through these handlers, so that they can keep their states updated. Since these handlers have state information, they're powerful! (for instance, we could have a handler to locally maintain issues/PRs matching a query, or keep track of open PRs so that they can be pinged/closed based on their inactivity, or respond to comments by linking known issues based on some pattern, etc.).

The database for the sync handlers is usually a local JSON store, but if you have the `DATABASE_URL` environment variable set up (which Heroku does), then that will be used instead.

All the handlers have per-repo configuration. There's a `config.json` local to every handler, which determines how it should respond to an event. The `"active"` key tells whether the handler should be considered while processing an event-related payload, and `"repos"` (may) contain the per-repo config. Repository names are usually of the form `"owner/repo"`, but since it allows regex patterns, you can have dangerous matches like `"owner/"` (which matches all the repos of an owner) and `".*"` (which matches any installation, i.e., every payload it gets). And, there's a `"sync"` key which tells whether it's a sync handler (disabling this will skip the runner from calling the handler).

There's also a global [`config.json`](https://github.com/servo-automation/highfive/blob/master/cgi-bin/config.json) where we can enable/disable a group of handlers corresponding to an event.

### Tests

The testsuite can be run offline with `python cgi-bin/test.py`. **Every enabled handler should have at least one test!** (the testsuite enforces this rule). The tests are pretty simple. The test payloads live inside `tests` directory, which has the same structure as that of `handlers`. Each test JSON has the `"initial"` and `"expected"` values, along with the actual `"payload"` (the one posted by Github). Once a handler handles a payload, the final values are asserted against the expected values. The `initial` and `expected` values can also be a list, so that we can test multiple cases with the same payload.

Github's payload JSONs are huge! They have a lot of useful information, but we won't be using most of them. In order to keep the test JSONs as precise as possible, there's a ["mark and sweep" cleaner](https://github.com/servo-automation/highfive/blob/master/cgi-bin/helpers/json_cleanup.py), which uses a wrapper type for finding those unused nodes. So, whenever we "get" a value corresponding to a key, the path is traced and marked. In the end, the unmarked values (or untraced paths) are thrown as errors by the testsuite. If you've added a new test, then the unused nodes can be cleaned up by running `python test.py write`.

`NodeMarker` is a *creepy* container. It wraps around all the objects! While most of the commonly used methods should work right now, in case you need to use a type-specific method (`lower` for `str`, for example), then you should add a new method to `NodeMarker`, asking it to access the method on the underlying type ([like so](https://github.com/servo-automation/highfive/blob/8691a1ce0dce6045194f2a5510c0f63d2da72804/helpers/json_cleanup.py#L50-L51)). So, instead of working around in the main code, we're introducing workarounds in the cleaner. Well, everything comes at a cost!

### Required events (and their corresponding handlers):

#### [`issue_comment`](https://developer.github.com/v3/activity/events/types/#issuecommentevent)
 - `comment_watcher`: A generic handler watches out for Github links that point to `master` branch (rather than a specific revision) and edits those comments (besides that, there are a bunch of handlers specific to Servo).
 - **Note:** This event is also required for `pull_request/open_pulls`

#### [`issues`](https://developer.github.com/v3/activity/events/types/#issuesevent)
 - `easy_assigned` (sync): This doesn't have a general configuration. This tracks the issues tagged `E-easy` (in Servo), assigns those issues to newcomers, tracks their PRs, pings them after a timeout, and unassigns the issues based on their inactivity.
 - `label_notify`: Notify label watcher(s) in a comment when a label is added to an issue.
 - `label_response`: Comment when a label is added to an issue.

#### [`pull_request`](https://developer.github.com/v3/activity/events/types/#pullrequestevent)
 - `assign_people`: Assign people based on review requests in PR body or (pseudo-)random reviewer rotation. It also welcomes new contributors who make PRs for the first time.
 - `diff_check_warn`: Check the diff of the commits in a PR for added lines, changed files, or missing tests matching a pattern (specified in the config), and post a consolidated warning message on the match(es) found.
 - `label_response`: Add/remove labels when a PR is opened/updated/closed.
 - `open_pulls` (sync): This manages all open PRs in queue. It tracks the PR update times and notifies its authors or closes the PRs based on their inactivity.
 - `path_watchers`: Notify watcher(s) in a comment whenever a PR makes changes to the "watched" paths.
 - `weekly_update` (sync): Collect statistics over a week and open an issue in the specified repo on a given day. For now, this tracks the PRs and newcomers appeared in a week. This is used for "[This Week in Servo](https://blog.servo.org/)".

---

### Installation (Generic)

- Clone this repo.
- [Create an integration](https://github.com/settings/integrations/new) for your account/organization (currently, highfive needs read/write permissions for all `issues` and `pull_request` events).
- Generate a private key for your integration (it's necessary to get the auth token for making API requests).
- Generate a random key and put it in the "secret" box of your integration. When Github sends the payload, its [HMAC-SHA1 signature](https://developer.github.com/webhooks/securing/) will be verified by the script on execution.
- Finally, grab the integration ID from your integration's settings page.
- Update the the global `config.json` with the PEM key, secret, the integration ID, the core contributors, and remove the events which you don't wanna handle. Make appropriate changes to `config.json` in the individual handlers.<sup>[1]</sup>
- Fill in the webhook URL.
- Create the integration, and now you'll be be able to install the integration in any repo/org you have admin access to.

### Heroku

- Create an app at Heroku, `cd` into this repo, and use the [toolbelt](https://devcenter.heroku.com/articles/heroku-command-line) to set the remote to your heroku app: <br /> `heroku git:remote -a <app-name>`
- Follow the steps from the generic installation.
- Commit and push to Heroku!
- The webhook URL is your Heroku app's URL.

**Note:** Ideally, you shouldn't share your PEM key or the secret with anyone (not even Heroku), but for the sake of making this thing to work, we don't have a choice. If you've got your own server, then there's nothing to worry about :)

### Docker

 - Clone the repo.
 - Make appropriate changes to the `config.json` belonging to the individual handlers.
 - Run `docker build -t highfive` to build the image.<sup>[2]</sup>
 - Assuming we the following directory structure,

```
$HOME
 |- highfive-config
    |- config.json
    |- highfive.pem
 |- json_dumps
    |- ...
```

 - Make changes to the global `config.json` and have absolute paths for `pem_file` and `dump_path` (say, `"/config/highfive.pem"` and `"/dumps"`).
 - Spawn a container with the config and dump paths appropriately mounted like so...

```
docker run -v ~/highfive-config:/config -v ~/json_dumps:/dumps -p 5000:5000 -d highfive
```

 - Whenever you rebuild an image or change the config, simply restart the container.

<br />

<sup>
[1]: If you've removed an event from the global config file, then the entire group of handlers will be ignored. <br />
[2]: Note that the handler-specific `config.json` live alongside the handlers themselves, and hence they cannot be changed after building the image.
</sup>
