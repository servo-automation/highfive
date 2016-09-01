## About highfive

Highfive is a bot, which is meant to provide a welcoming environment for the newcomers, and also help the contributors by commenting, labeling or notifying them in issues and pull requests when an anticipated event occurs.

The stuff inside this repo (and all its sub-repos) is basically a rework (and refactor) of all the collaborative work done in the old [highfive](https://github.com/servo/highfive), considering the limitations of the Github API.

This repo (hooker) is responsible for calling the various handlers with the payload "posted" by Github webhooks API.

### Design

Calling `python runner.py` starts a Flask-based server, which listens to a particular port for `POST`ing of payloads. The whole thing can be tested lively at [Heroku platform](http://heroku.com/). Their free plan kills the server after a few minutes of inactivity, but when a payload is posted, the script will be executed and the payload be handed over to the server. The initial startup delay isn't much, and hence it best suites our purpose.

All the payload handlers live inside `handlers`, grouped into submodules corresponding to each [webhook event](https://developer.github.com/webhooks/#events), so that we'll know which event triggers a handler, or in other words, which events have to be enabled while setting up a new webhook. Most often, we definitely don't wanna go for the "Send me everything" option that Github offers for a webhook, which thrashes your server with payloads related to every single event!

There's a `config.json` inside every handler, which has the configuration related to a particular handler. They all share the `"active"` key, which tells whether the handler should be considered while processing the payload. There's also a global [`config.json`](https://github.com/servo-highfive/hooker/blob/master/config.json) where we can enable/disable a group of handlers corresponding to an event. When multiple accounts and auth tokens are listed inside the global config, an user-token pair is chosen randomly just before handling a payload (so that the API requests are shared by multiple bots).

The test payloads live inside `tests`. The directory has the same structure as that of the `handlers`, except that payload JSONs are present instead of handlers. The testsuite can be run offline with `python test.py`. Each test JSON has `"initial"` and `"expected"` values, along with the actual `"payload"`. Once a handler is executed, the final values are asserted against the expected values.

### Supported handlers

#### [`issues`](https://developer.github.com/v3/activity/events/types/#issuesevent)
 - `label_response`: Comment when a configured label is added to an issue
 - `label_notify`: Notify a label watcher in comment when a configured label is added to an issue

---

### Installation (Heroku)

- Clone this repo.
- Create one (or more) Github account(s) for bot(s). Generate the corresponding auth tokens with the necessary [scopes](https://developer.github.com/v3/oauth/#scopes). A bot should (at least) have the `repo` scope for the handlers to work.
- Update the global `config.json` with the account name(s) and auth token(s)<sup>[1]</sup> and remove the events which you don't wanna handle. Update the `config.json` in the individual handlers appropriately<sup>[2]</sup>
- Create an app at Heroku, `cd` into the repo's directory, and use the [toolbelt](https://devcenter.heroku.com/articles/heroku-command-line) to set the remote to your heroku app like so, `heroku git:remote -a <app-name>`.
- Push to heroku!
- Go to the settings page of your repo, open "webhooks and services" and add a new webhook.
- Point the payload URL to your heroku app's URL. The content type should be `application/json`. Choose "Let me select individual events" and select only those events you've enabled in the global config file.<sup>[3]</sup>

<sup>
[1]: It's not a good idea to disclose the token publicly. <br /.>
[2]: If you've removed an event from the global config file, then the entire group of handlers will be ignored. <br /.>
[3]: A clever strategy would be to have multiple apps, each taking care of a webhook event (or a set of handlers). <br />
</sup>
