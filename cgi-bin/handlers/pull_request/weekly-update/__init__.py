from datetime import datetime, timedelta
from dateutil.parser import parse as datetime_parse

import calendar

def default():
    return {
        "newcomers": [],            # newcomer handles
        "pulls": [],                # PR numbers
        "started_from": None,       # date from which we started counting
        "post_date": None,          # date on which the post should be committed
        "last_updated": None,       # last updation timestamp
    }


def check_state(api, config, db, inst_id, name):
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
    # TODO: Prepare post, commit and open PR

    # Removing the data, so that next time a PR is opened, we'll start afresh
    api.logger.debug('Removing existing data...')
    db.remove_obj(inst_id, self_name)


def check_payload(api, config, db, inst_id, name):
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
        data['started_from'] = data['last_updated'] = str(now)
        day, time = config['next_pr_day_time'].split()
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
        data['last_updated'] = str(now)

    if data != old_data:
        db.write_obj(data, inst_id, self_name)


def payload_handler(api, config, db, inst_id, name):
    config = api.get_matches_from_config(config)
    if config:
        check_payload(api, config, db, inst_id, name)
