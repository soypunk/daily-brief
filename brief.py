#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import codecs
import json
import smtplib
from smtplib import SMTPException
import feedparser
import summarize
import argparse
import time
import re
from pprint import pprint
from email.mime.text import MIMEText
from HTMLParser import HTMLParser


__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
CONFIG = None
NOW = time.localtime()


class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()


def load_config():
    config_file = open(os.path.join(__location__, 'brief.config'))
    config = json.load(config_file)
    config_file.close()
    return config


def greeting():
    morning = 12
    afternoon = 18
    evening = 24
    current_hour = int(time.strftime("%H", NOW))
    if current_hour < morning:
        return "morning"
    elif morning <= current_hour < afternoon:
        return "afternoon"
    else:
        return "evening"


def nltk_prep():
    import nltk
    nltk.download('stopwords')
    nltk.download('punkt')


def fetch_weather():
    weather_report = feedparser.parse(CONFIG['feeds']['weather'])
    long_forecast = weather_report.entries[0].title
    short_forecast = long_forecast.split(' at ', 1)[0]
    # the NWS forecast gives you a temp like 43 F and OS X/iOS reads it daftly.
    short_forecast = re.sub(r'^(.*)\s([+-]?[0-9]+)\s?([CF])$', r'\1 \2 degrees', short_forecast)
    return short_forecast


def fetch_headlines(greeting):
    headlines = feedparser.parse(CONFIG['feeds']['headlines'])
    text = []
    text.append(u"Here are this %s\'s headlines:\r\n\r\n" % (greeting))
    ss = summarize.SimpleSummarizer()
    stories_to_skip = ['Review: ']
    for entry in headlines.entries:
        for skip in stories_to_skip:
            if entry.title.startswith(skip):
                continue
            text.append(u''.join(entry.title + ":\r\n"))
            title_lower = entry.title.lower()
            summary_lower = entry.summary.lower()
            if title_lower != summary_lower:
                summary = strip_tags(entry.summary)
                summary = ss.summarize(summary.encode('utf-8'), 2)
                text.append(u''.join([summary.decode('utf-8'), "\r\n"]))
                text.append("\r\n\r\n")
            # "Use Embedded Speech Commands to Fine-Tune Spoken Output"
            #text.append(u"[[slnc 400]]\r\n")
    return text


def prepare_msg(msg_text):
    text = u''.join(msg_text)
    return MIMEText(text.encode('utf-8'), 'plain', 'utf-8')


def prepare_email(msg, subject, from_addr, to_addr):
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_addr
    return msg


def send_email(email, host):
    # Send the message via our own SMTP server, but don't include the
    # envelope header.
    s = smtplib.SMTP(host)
    s.sendmail(email['From'], email['To'], email.as_string())
    s.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--to-text", help="output to stdout instead of sending an email", action='store_true')
    parser.add_argument("--nltk-first-run", help="download NLTK corpora", action='store_true')
    args = parser.parse_args()
    
    # just install the nltk junk
    if args.nltk_first_run:
        nltk_prep()
        sys.exit()
    
    CONFIG = load_config()
    
    greeting = greeting()
    msg_text = []
    msg_text.append(u"Good %s, %s. It is %s.\r\n\r\n" % (greeting, CONFIG['name'], fetch_weather()))
    
    msg_text.extend(fetch_headlines(greeting))
    msg = prepare_msg(msg_text)
    
    if args.to_text:
        for msg in msg_text:
            sys.stdout.write(msg.encode('utf-8'))
    else:
        try:
            email = prepare_email(msg, 'Daily Briefing', CONFIG['from'], CONFIG['to'])
            send_email(email, CONFIG['smtp']['host'])
            #print "Email sent"
            print ""
        except SMTPException:
            #print "Error: unable to send email"
            print ""
