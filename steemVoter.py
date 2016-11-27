#!/usr/bin/python3

from piston.steem import Steem
from piston.steem import BroadcastingError
from datetime import datetime
from datetime import timedelta
import argparse
import hashlib
import os
import time
import pymysql.cursors

os.environ['UNLOCK'] = "******************"
os.environ['PATH'] += "******************"

# get current folder ready
os.chdir(os.path.dirname(__file__))

# start parsing command line arguments
parser = argparse.ArgumentParser()

# command line arguments
parser.add_argument("-v", "--verbose", help="Turn on verbose", default=False, action="store_true")
parser.add_argument("-m", "--mock", help="Turn on verbose", default=False, action="store_true")
args = parser.parse_args()

# constants and other variables
STEEM_MAX_POSTS_REQUEST = 100  # Number of posts to gather from steem each loop. 100 = Max
hash_func = hashlib.md5  # Set the hashing function to MD5.


def load_past_votes():
    with connection.cursor() as this_cursor:
        this_cursor.execute(
            "SELECT * FROM `SteemVotingLogs` WHERE NOW() <= DATE_ADD(dateTime, INTERVAL 1 HOUR) AND (`success`=1 OR `hasFailed`>=3)")
        result = this_cursor.fetchall()

    new_list = []
    for entry in result:
        new_list.append(hash_func((entry["accountName"] + entry["post"]).encode()).hexdigest())
    return new_list


def has_already_voted(this_post, this_user, list_of_past):
    new_hash = hash_func((this_user["accountName"] +
                         "@" + this_post['author'] + "/" + this_post['permlink']).encode()).hexdigest()
    if new_hash in list_of_past:
        if args.verbose:
            print("  PASSING: Already voted.", this_user["accountName"], " -> ",
                  "@" + this_post['author'] + "/" + this_post['permlink'])
        return True
    return False


def apply_vote(this_post, this_user, list_of_past):
    post_identifier = "@" + this_post['author'] + "/" + this_post['permlink']
    try:

        if not args.mock:
            this_post['vote'](this_user['votePower'], voter=this_user["accountName"])
        if args.verbose:
            print("+ SUCCESS:", this_user["accountName"], "voted", this_post['author'], " -> ", post_identifier)
        list_of_past.append(hash_func((this_user["accountName"] + post_identifier).encode()).hexdigest())

        try:
            with connection.cursor() as this_cursor:
                if not args.mock:
                    this_cursor.execute(
                        """INSERT INTO SteemVotingLogs
                        (ruleID, accountName, post, link, votingPower, success, articleDateTime, dateTime) VALUES
                        ({0}, '{1}', '{2}', '{3}', {4}, {5}, FROM_UNIXTIME({6}), FROM_UNIXTIME({7}))
                        ON DUPLICATE KEY UPDATE `success`={5}, dateTime='FROM_UNIXTIME({7})'
                        """.format(
                            this_user["ruleID"],
                            str(this_user['accountName']),
                            post_identifier,
                            "https://steemit.com/" + this_post["category"] + "/" + post_identifier + "/",
                            this_user['votePower'],
                            1,
                            int(time.mktime(datetime.strptime(post['created'], "%Y-%m-%dT%H:%M:%S").timetuple()))-time.timezone,
                            int(time.time())
                        )
                    )
        except Exception as e:
            if args.verbose:
                print("failed to write to database...", e)
    except BroadcastingError:
        if args.verbose:
            print("- FAILED: Skipping...", this_user["accountName"], " -> ", post_identifier)
        try:
            with connection.cursor() as this_cursor:
                if not args.mock:
                    this_cursor.execute(
                        """INSERT INTO `SteemVotingLogs`
                        (ruleID, accountName, post, link, votingPower, hasFailed, articleDateTime, dateTime) VALUES
                        ({0}, '{1}', '{2}', '{3}', {4}, {5}, FROM_UNIXTIME({6}), FROM_UNIXTIME({7}))
                        ON DUPLICATE KEY UPDATE `hasFailed`=`hasFailed`+1
                        """.format(
                            this_user["ruleID"],
                            str(this_user['accountName']),
                            post_identifier,
                            "https://steemit.com/" + this_post["category"] + "/" + post_identifier + "/",
                            this_user['votePower'],
                            1,
                            int(time.mktime(datetime.strptime(post['created'], "%Y-%m-%dT%H:%M:%S").timetuple()))-time.timezone,
                            int(time.time())
                        )
                    )
        except Exception as e:
            if args.verbose:
                print("failed to write to database...", e)
    except Exception as e:
        print("ERROR:", e)
        if args.verbose:
            print("* FAILED:", post_identifier)


if __name__ == '__main__':
    """Run the steem voter for authors"""
    # connect to the database
    connection = pymysql.connect(host='******************',
                                 user='******************',
                                 password='******************',
                                 db='******************',
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)

    with connection.cursor() as cursor:
        cursor.execute("""SELECT SteemAccountRules.id AS ruleID, accountName, author, votePower, delay FROM `SteemAccountRules`
                        INNER JOIN `SteemAccounts` USING (userID) WHERE SteemAccounts.isActive=1 ORDER BY SteemAccounts.dateAdded""")
        userRules = cursor.fetchall()

    steem = Steem("wss://node.steem.ws")  # Create steem object.
    max_time_reached = False  # when max time reached
    last_identifier = None  # store last identifier for next loop
    post_min_time = timedelta(minutes=0)
    post_max_time = timedelta(minutes=35)
    this_list = load_past_votes()
    while not max_time_reached:
        if last_identifier is not None:
            # Get new posts starting at the last one
            results = steem.get_posts(limit=STEEM_MAX_POSTS_REQUEST, sort='created', start=last_identifier)
        else:
            # Get the new posts, starting at the beginning
            results = steem.get_posts(limit=STEEM_MAX_POSTS_REQUEST, sort='created')  # Get new posts
        for post in results:
            # Generate the hash for the identifier:
            last_identifier = post['identifier']
            # Determine amount of specified amount of time has passed since
            # the post was created.
            t1 = datetime.strptime(post['created'], "%Y-%m-%dT%H:%M:%S")
            t2 = datetime.utcnow()
            td = t2 - t1
            if td <= post_min_time:
                continue
            elif td >= post_max_time:
                # if its in the list, remove it.
                max_time_reached = True
                continue
            else:
                for user in userRules:
                    if user['accountName'] is post['author']:
                        continue
                    if user['author'] == 'steemvoter':
                        continue
                    if (post['author'] == user['author']) and has_already_voted(post, user, this_list):
                        continue
                    if (post['author'] == user['author']) and (td > timedelta(minutes=user['delay'])):
                        apply_vote(post, user, this_list)
                        continue
