## Highfive

[![Build Status](https://travis-ci.org/servo-automation/highfive.svg?branch=master)](https://travis-ci.org/servo-automation/highfive)

Highfive is a Github integration (bot), meant to provide a welcoming environment for the newcomers to open source, and also help the contributors by commenting, labelling or notifying them in issues and pull requests when an anticipated event occurs. This is a rewrite of all the collaborative work done in the old [highfive](https://github.com/servo/highfive), with the limitations of Github API in mind.

### Usage

All handlers live inside `event_handlers`, grouped into directories corresponding to each [webhook event](https://developer.github.com/webhooks/#events), so that we'll know which event triggers a handler, or in other words, which events have to be enabled while setting up a new integration. We definitely don't wanna check all the permissions offered by Github, as it thrashes your server with payloads from every single event!

By default, the handlers have access to the store through the `APIProvider` class. The default store is a JSON store, which allows handlers to have their own JSON objects. If you have a PostgreSQL database, then you can use it by setting its URL in the `DATABASE_URL` environment variable.

All the handlers have per-repo configuration. There's a `config.json` local to every handler, which determines how it should respond to an event. The `"active"` key tells whether the handler should be considered while processing an event-related payload (i.e., whether it's enabled). Some handlers offer per-repo config, where the repository names are usually of the form `"owner/repo"`, but since we also support regex patterns, you can have dangerous matches like `"owner/"` (which matches all the repos of an owner) and `".*"` (which matches every payload it gets, which is definitely not what you'd want!).

Finally, there's a global [`config.json`](./highfive/config.json) which holds some stuff for highfive to function properly (like the integration ID, secret, PEM key location, etc.). We can also add/remove events in the file which enables/disables entire groups of handlers. Also, if the file contains values in the form `ENV::NAME`, then `$NAME` will be obtained from the environment. This is particularly useful if you don't wanna dump all the secret stuff in the config.

### Running

Calling `python serve.py` starts a Flask server, which listens to a particular port for `POST`ing of payloads. It can be tested lively at [Heroku platform](https://heroku.com/) (see below for installation). Their free plan kills the server after a few minutes of inactivity, but once a payload is posted, the script will be executed and the payload will be handed over to the server. So, it works for us.

### Required events (and their corresponding handlers):

An event should be enabled (in Github API and the config) for the handlers listed under that event.

#### [`issue_comment`](https://developer.github.com/v3/activity/events/types/#issuecommentevent)
 - `github_permalink_finder`: This checks for Github URLs in comments and expands them to their canonical form (if required).
 - `servo_bors_labeller`: Servo-specific handler for updating labels based on the comment from merge bot.
 - `servo_log_checker`: Servo-specific handler for checking logs from the build bot based on failure comments posted by the merge bot.
 - `servo_reviewer_assigner`: Servo-specific handler for assigning reviewers based on review request and approvals made on comments.
 - **Note:** This event is also required for `issues/easy_issue_assigner` and `pull_request/open_pull_watcher` handlers.

#### [`issues`](https://developer.github.com/v3/activity/events/types/#issuesevent)
 - `easy_issue_assigner`: Tracks issues with a specific label (`E-easy` in Servo), assigns those issues to newcomers, tracks their PRs, pings them after a timeout, unassigns the issues based on their inactivity.
 - `label_notifier`: Pokes user(s) in a comment when a label watched by the user(s) is added to an issue.

#### [`pull_request`](https://developer.github.com/v3/activity/events/types/#pullrequestevent)
 - `commit_diff_checker`: This checks the diff of commits in a PR for added lines, changed files or missing tests matching a pattern (in the config) and posts a warning about the matched items.
 - `label_responder`: Adds/removes labels when a PR is opened/updated/merged.
 - `open_pull_watcher`: This manages all open PRs in queue. It tracks the PR updates and notifies its authors or closes the PRs based on their inactivity.
 - `path_watcher_notifier`: Notifies users(s) in a comment whenever a PR makes changes to path(s) watched by the user(s).
 - `reviewer_assigner`: Assigns people based on review requests in PR body or (pseudo-)random reviewer rotation. It also welcomes new contributors who make PRs for the first time.
 - `servo_metadata_checker`: Servo-specific handler to post warnings when a PR makes changes to WPT directory without adding metadata.
 - `twis_updater`: Collects statistics over a week and opens an issue in the specified repo on a given day. For now, this tracks the PRs and newcomers appeared in a week. This is used for "[This Week in Servo](https://blog.servo.org/)".

---

### Installation (Setup)

- Clone this repo.
- [Create an integration](https://github.com/settings/integrations/new) for your account/organization (currently, highfive needs read/write permissions for all `issues` and `pull_request` events).
- Generate a private key for your integration (it's necessary to get the auth token for making API requests).
- Generate a random key and put it in the "secret" box of your integration. When Github sends the payload, its [HMAC-SHA1 signature](https://developer.github.com/webhooks/securing/) will be verified by the script on execution.
- Finally, grab the integration ID from your integration's settings page.
- Update the the global `config.json` with the PEM key, secret, the integration ID, the core contributors, etc. Make appropriate changes to `config.json` in the individual handlers.<sup>[1]</sup>
- Fill in the webhook URL.
- Create the integration, and now you'll be be able to install the integration in any repo/org you have admin access to.

Once you have this, you can do any of the following.

### Heroku

- Create an app at Heroku, `cd` into this repo, and use the [toolbelt](https://devcenter.heroku.com/articles/heroku-command-line) to set the remote to your heroku app: <br /> `heroku git:remote -a <app-name>`
- Commit and push to Heroku!
- The webhook URL is your Heroku app's URL.

**Note:** Ideally, you shouldn't share your PEM key or the secret with anyone (not even Heroku), but for the sake of making this thing to work, we don't have a choice. If you've got your own server, then there's nothing to worry about :)

### Docker

 - Run `docker build -t highfive` to build the image.<sup>[2]</sup>
 - Assuming we have the following directory structure and the `config.json` from upstream,<sup>[3]</sup>

```
$HOME
 |- highfive.pem
 |- json_dumps
    |- ...
```

 - Spawn a container with the config and dump paths appropriately mounted like so...

```
docker run -v ~/highfive.pem:/highfive.pem:ro -v ~/json_dumps:/dumps -e PEM_KEY="/highfive.pem" -e SECRET="$SECRET" -e ID=$ID -e DUMP_PATH="/dumps" -e IMGUR_CLIENT_ID=$CLIENT_ID -e SCREENSHOTS_IP="http://$SHOTS_IP:$SHOTS_PORT" -p 8000:8000 -d highfive
```

 - Whenever you rebuild an image or change the config, simply restart the container.

<br />

<sup>
[1]: If you've removed an event from the global config file, then the entire group of handlers will be ignored. <br />
[2]: Note that the handler-specific `config.json` live alongside the handlers themselves, and hence they cannot be changed after building the image.
[3]: If you've modified the config, then you can specify the new location using the `CONFIG` env variable.
</sup>
