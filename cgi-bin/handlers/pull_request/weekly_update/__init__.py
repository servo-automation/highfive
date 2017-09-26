from copy import deepcopy
from datetime import datetime, timedelta
from dateutil.parser import parse as datetime_parse

from helpers.methods import Modifier, join_names

import calendar

TEMPLATE = '''
{assignees}: Here are the stats for this week.

Link to pulls: https://github.com/pulls?utf8=%E2%9C%93&q=is%3Apr+is%3Amerged+closed%3A{start}..{end}+user%3A{owner}

New contributors in {owner}/{repo}:

{newcomers}

'''

def default():
    return {
        "newcomers": [],            # newcomer handles
        "pulls": [],                # PR numbers
        "started_from": None,       # date from which we started counting
        "post_date": None,          # date on which the post should be committed
    }


def check_state(api, config, db, inst_id, self_name):
    data = db.get_obj(inst_id, self_name)
    if data.get('owner') and data.get('repo'):
        api.owner, api.repo = data['owner'], data['repo']
    else:   # We pass a fake payload here (so, owner and repo should be valid to proceed)
        api.logger.debug('No info about owner and repo in JSON. Skipping this cycle...')
        return

    post_date = datetime_parse(data['post_date'])
    now = datetime.now(post_date.tzinfo)
    config = api.get_matches_from_config(config)
    if not config:
        return

    if now < post_date:
        return

    api.logger.debug('Preparing to post weekly update...')
    assignees = join_names(map(lambda n: '@' + n, config['assignees']))
    week_end = datetime_parse(data['post_date'])
    week_start = str((week_end - timedelta(days=7)).date())
    week_end = str(week_end.date())
    newcomers = '\n'.join(map(lambda c: ' - @' + c, data['newcomers']))

    body = TEMPLATE.format(assignees=assignees, newcomers=newcomers,
                           start=week_start, end=week_end,
                           owner=data['owner'], repo=data['repo'])
    title = config['issue_title'].format(date=week_end)

    owner, repo = config['repo'].split('/')
    with Modifier(api, owner=owner, repo=repo) as new_api:
        new_api.create_issue(title=title, body=body,
                             assignees=config.get('assignees', []),
                             labels=config.get('labels', []))

    # Removing the data, so that next time a PR is opened, we'll start afresh
    api.logger.debug('Removing existing data...')
    db.remove_obj(inst_id, self_name)


def check_payload(api, config, db, inst_id, self_name):
    payload = api.payload
    action = payload.get('action')
    if action is None:
        return check_state(api, config, db, inst_id, self_name)

    if not api.is_pull:
        return

    now = datetime.now()
    data = db.get_obj(inst_id, self_name)
    old_data = deepcopy(data)

    if not data:
        data = default()
        data['started_from'] = str(now)
        day, time = config['notify_day_time'].split()
        day = day[:3]
        weekday = list(calendar.day_abbr).index(day)
        days_ahead = weekday - now.weekday()
        if days_ahead <= 0:     # this week's already gone
            days_ahead += 7

        dt = datetime(now.year, now.month, now.day) + timedelta(days=days_ahead)
        dt = datetime_parse(str(dt) + ' ' + time)
        data['post_date'] = str(dt)
        api.logger.debug('Handler scheduled to post on %s' % dt)

    if data.get('owner') is None and api.owner:
        data['owner'] = api.owner
    if data.get('repo') is None and api.repo:
        data['repo'] = api.repo

    if action == 'closed' and api.payload['pull_request'].get('merged'):
        data['pulls'].append(api.issue_number)
        contributors = api.get_contributors()
        if api.creator not in contributors:
            data['newcomers'].append(api.creator)

    if data != old_data:
        db.write_obj(data, inst_id, self_name)


def payload_handler(api, config, db, inst_id, name):
    config = api.get_matches_from_config(config)
    if config:
        check_payload(api, config, db, inst_id, name)
