from ... import EventHandler, Modifier
from copy import deepcopy
from datetime import datetime, timedelta
from dateutil.parser import parse as datetime_parse

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


class TwisUpdater(EventHandler):
    '''
    Stateful handler for tracking this installation's statistics. Then, this opens an issue in a
    configured repo with that data on a specific day in a week. Currently, this collects the list
    of newcomers to this repo.
    '''

    def __init__(self, api, config):
        super(TwisUpdater, self).__init__(api, config)
        self.now = datetime.now()
        self._load_data()


    def _load_data(self):
        '''Initialize store data and set defaults if necessary.'''

        self.data = self.get_object()
        self.old_data = deepcopy(self.data)
        self._init_data()
        if self.data.get('owner') is None and self.api.owner:
            self.data['owner'] = self.api.owner
        if self.data.get('repo') is None and self.api.repo:
            self.data['repo'] = self.api.repo


    def _init_data(self):
        '''Initialize data (if it wasn't already) to schedule the day to open the issue.'''

        if self.data:
            return

        config = self.get_matched_subconfig()
        self.data['started_from'] = str(self.now)
        day, time = config['notify_day_time'].split()
        day = day[:3]
        weekday = list(calendar.day_abbr).index(day)
        days_ahead = weekday - now.weekday()
        if days_ahead <= 0:     # this week's already gone
            days_ahead += 7

        dt = datetime(now.year, now.month, now.day) + timedelta(days=days_ahead)
        dt = datetime_parse(str(dt) + ' ' + time)
        self.data['post_date'] = str(dt)
        self.logger.info('Handler scheduled to post on %s' % dt)


    def on_next_tick(self):
        if self.data.get('owner') is None or self.data.get('repo') is None:
            self.logger.debug('No info about owner and/or repo in JSON. Skipping this cycle...')
            return

        post_date = datetime_parse(self.data['post_date'])
        now = datetime.now(post_date.tzinfo)
        if now < post_date:
            return

        with Modifier(self.api, owner=self.data['owner'], repo=self.data['repo']):
            self._prepare_for_update()


    def on_issue_closed(self):
        if not (self.api.is_pull and self.api.payload['pull_request'].get('merged')):
            return

        self.data['pulls'].append(self.api.number)
        contributors = self.api.get_contributors()
        if self.api.creator not in contributors:
            self.data['newcomers'].append(self.api.creator)


    def cleanup(self):
        if self.data != self.old_data:
            self.write_object(self.data)


    def _prepare_for_update(self):
        config = self.get_matched_subconfig()
        if not config:
            return

        self.logger.info('Preparing to post weekly update...')
        assignees = self.join_names(map(lambda n: '@' + n, config['assignees']))
        week_end = datetime_parse(self.data['post_date'])
        week_start = str((week_end - timedelta(days=7)).date())
        week_end = str(week_end.date())
        newcomers = '\n'.join(map(lambda c: ' - @' + c, self.data['newcomers']))

        title = config['issue_title'].format(date=week_end)
        body = TEMPLATE.format(assignees=assignees, newcomers=newcomers,
                               start=week_start, end=week_end,
                               owner=self.data['owner'], repo=self.data['repo'])

        owner, repo = config['repo'].split('/')
        with Modifier(self.api, owner=owner, repo=repo):
            self.api.create_issue(title=title, body=body,
                                  assignees=config.get('assignees', []),
                                  labels=config.get('labels', []))

        # Removing the data, so that next time a PR is opened, we'll start afresh
        self.logger.info('Removing existing data...')
        self.remove_object()


handler = TwisUpdater
