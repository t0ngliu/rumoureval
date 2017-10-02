"""
Manages importing data into basic Python structures.
"""

import logging
import json
import os
import sys

from util.lists import filter_none
from objects.tweet import Tweet

LOGGER = logging.getLogger()

def get_script_path():
    """
    Get the root path which the script was run from.
    :rtype:
        `str`
    """
    return os.path.dirname(os.path.realpath(sys.argv[0]))

def import_thread(folder):
    """
    Imports a single twitter thread following a specific structure into a `dict`.
    Assumes the following structure:

    folder
    |- structure.json
    |- urls.dat
    |- source-tweet
        |- <tweet_id>.json
    |- replies
        |- <tweet_id>.json
        |- ...
    |- context
        |- wikipedia
        |- urls
            |- <url_md5>
            |- ...
    :param folder:
        folder name to retrieve source tweet from
    :type folder:
        `str`
    :rtype:
        `dict`
    """
    thread = {}

    with open(os.path.join(folder, 'structure.json')) as structure:
        thread['structure'] = json.load(structure)

    with open(os.path.join(folder, 'urls.dat')) as url_dat:
        thread['urls'] = []
        for line in url_dat.readlines():
            raw_url = line.split()
            url = {
                'hash': raw_url[0],
                'short': raw_url[1],
                'full': raw_url[2],
            }
            thread['urls'].append(url)

    for child in os.listdir(os.path.join(folder, 'source-tweet')):
        with open(os.path.join(folder, 'source-tweet', child)) as source_tweet:
            thread['source'] = json.load(source_tweet)

    thread['replies'] = {}
    for child in os.listdir(os.path.join(folder, 'replies')):
        with open(os.path.join(folder, 'replies', child)) as reply_tweet_file:
            reply_tweet = json.load(reply_tweet_file)
            thread['replies'][reply_tweet['id_str']] = reply_tweet

    if os.path.exists(os.path.join(folder, 'context', 'wikipedia')):
        with open(os.path.join(folder, 'context', 'wikipedia')) as wiki:
            thread['wiki'] = wiki.read()
    else:
        thread['context/wiki'] = None

    if os.path.exists(os.path.join(folder, 'context', 'urls')):
        thread['context/urls'] = {}
        for child in os.listdir(os.path.join(folder, 'context', 'urls')):
            with open(os.path.join(folder, 'context', 'urls', child)) as url_context:
                thread['context/urls'][child] = url_context.read()
    else:
        thread['context/urls'] = None

    if os.path.exists(os.path.join(folder, 'urls-content')):
        thread['urls-content'] = {}
        for child in os.listdir(os.path.join(folder, 'urls-content')):
            with open(os.path.join(folder, 'urls-content', child)) as url_content:
                thread['urls-content'][child] = url_content.read()
    else:
        thread['urls-content'] = None

    return thread


def import_tweet_data(folder):
    """
    Imports raw tweet data from the given folder, recursively.
    :param folder:
        folder name to retrieve tweets from
    :type folder:
        `str`
    :rtype:
        `dict` or None
    """
    if not os.path.exists(folder):
        LOGGER.debug('File/folder does not exist: %s', folder)
        return None

    if os.path.isfile(folder):
        return None

    tweet_data = []
    children = os.listdir(folder)
    if 'structure.json' in children:
        # This is the root of a twitter thread
        tweet_data.append(import_thread(folder))
    else:
        for child in children:
            child_data = import_tweet_data(os.path.join(folder, child))
            if child_data is not None:
                tweet_data += child_data

    tweet_data = filter_none(tweet_data) # [x for x in tweet_data if x is not None]
    return tweet_data


def import_annotation_data(folder):
    """
    Imports raw annotation data for the specified data source, indicating the annotation
    for each tweet ID
    :param folder:
        folder of annotations
    :type folder:
        `str`
    :rtype:
        `dict`
    """
    task_a_annotations = {}
    task_b_annotations = {}
    with open(os.path.join(folder, 'subtaskA.json')) as annotation_json:
        task_a_annotations = json.load(annotation_json)
    with open(os.path.join(folder, 'subtaskB.json')) as annotation_json:
        task_b_annotations = json.load(annotation_json)
    return task_a_annotations, task_b_annotations


def build_tweet(tweet_data, tweet_id, structure, is_source=False):
    """
    Parses raw twitter data and creates Tweet objects, setting up their parent and child
    tweets according to the tweet_data structure.

    :param tweet_data:
        A single Twitter thread
    :type tweet_data:
        `dict`
    :param tweet_id:
        ID of tweet to build
    :type root_tweet_id:
        `str`
    :param structure:
        Structure that children tweets follow
    :type structure:
        `list` or `dict`
    :param is_source:
        True if the tweet is the source tweet of a thread, False otherwise
    :type is_source:
        `bool`
    :rtype:
        :class:`Tweet`
    """
    children = [
        build_tweet(
            tweet_data,
            child_tweet_id,
            structure[child_tweet_id]
        ) for child_tweet_id in structure
    ]
    children = filter_none(children)
    if is_source:
        return Tweet(tweet_data['source'], children=children)
    elif tweet_id in tweet_data['replies']:
        return Tweet(tweet_data['replies'][tweet_id], children=children)

    return None


def import_data(datasource):
    """
    Imports raw tweet data from the specified data source, to be parsed later.
    :param datasource:
        source of data to import
    :type datasource:
        either 'dev', 'train', or 'test'
    :rtype:
        `list` of `dict`, `dict`
    """
    source_folder = os.path.join(get_script_path(), '..', 'data', datasource)
    source_annotations = os.path.join(get_script_path(),
                                      '..', 'data', '{}-annotations'.format(datasource))
    tweet_data = import_tweet_data(source_folder)

    parsed_tweets = [
        build_tweet(
            thread,
            thread['source']['id_str'],
            thread['structure'][thread['source']['id_str']],
            is_source=True
        ) for thread in tweet_data
    ]

    annotation_data = import_annotation_data(source_annotations)
    return parsed_tweets, annotation_data
