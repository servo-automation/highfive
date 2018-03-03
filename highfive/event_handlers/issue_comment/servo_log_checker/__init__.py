from HTMLParser import HTMLParser
from ... import EventHandler

import json
import re

class ServoLogChecker(EventHandler):
    '''
    Failure comment from 'bors' looks something like:

    > ":broken_heart: Test failed - [linux2](http://build.servo.org/builders/linux2/builds/2627)"

    We get the relevant build result URL from this, fetch that log output and post the relevant
    part as a comment. Additionally, if it's a CSS failure, then we get the snapshot(s) from the
    raw log (using the reftest screenshot extractor), post the image to Imgur and link it in
    the comment.
    '''

    def _check_css_failures(self, build_url):
        data = self.api.get_screenshots_for_build(build_url)
        # Image data is the key because, there could be
        # different tests with same result.
        images = {}
        for img in data:
            images.setdefault(img['blend'], [])
            images[img['blend']].append('**%s** (test) **%s** (ref)' % \
                                        (img['test']['url'], img['ref']['url']))

        link = None
        comment = ('Hi! I was able to get the screenshots for some tests.'
                   " To show the difference, I've blended the two screenshots.")
        for img in images:
            link = self.api.post_image_to_imgur(img)
            if not link:
                continue

            tests = ', '.join(images[img])
            comment += '\n\n - %s\n\n![](%s)' % (tests, link)

        if link is not None:
            # We've uploaded at least one image (let's post comment)
            self.api.post_comment(comment)

    def on_new_comment(self):
        if self.api.sender != self.config["bors_name"]:
            return

        comment_patterns = self.config.get("failure_comment_patterns", [])
        if not any(re.search(pat, self.api.comment) for pat in comment_patterns):
            return

        url = re.findall(r'.*\((.*)\)', self.api.comment)
        if not url:
            return

        # Substitute and get the new url
        # (e.g. http://build.servo.org/json/builders/linux2/builds/2627)
        json_url = re.sub(r'(.*)(builders/.*)', r'\1json/\2', url[0])
        json_stuff = self.api.get_page_content(json_url)
        if not json_stuff:
            return

        build_stats = json.loads(json_stuff)
        failure_regex = r'Tests with unexpected results:\n(.*)\n</span><span'
        comments = []

        for step in build_stats['steps']:
            for name, log_url in step['logs']:
                if name != 'stdio':
                    continue

                stdio = self.api.get_page_content(log_url)
                failures = re.findall(failure_regex, stdio, re.DOTALL)

                if not failures:
                    continue

                try:
                    failures = HTMLParser().unescape(failures[0])
                except UnicodeDecodeError:
                    failures = HTMLParser().unescape(failures[0].decode('utf-8'))

                if 'css' in failures:
                    self._check_css_failures(url)

                comment = [' ' * 4 + line for line in failures.split('\n')]
                comments.extend(comment)

        if comments:
            self.api.post_comment('\n'.join(comments))


handler = ServoLogChecker
