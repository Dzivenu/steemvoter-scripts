#!/usr/bin/python3

import argparse
import subprocess
import pymysql.cursors
import os

os.environ['PATH'] += "******************"
os.environ['UNLOCK'] = "******************"

# get current folder ready
os.chdir(os.path.dirname(__file__))

# start parsing command line arguments
parser = argparse.ArgumentParser()

# command line arguments
parser.add_argument("-v", "--verbose", help="Turn on verbose", default=False, action="store_true")
parser.add_argument("-m", "--mock", help="Turn on verbose", default=False, action="store_true")
args = parser.parse_args()

if __name__ == '__main__':
    connection = pymysql.connect(host='******************',
                                 user='******************',
                                 password='******************',
                                 db='******************',
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT accountName FROM `SteemAccounts` WHERE `isActive`=1")
            result = cursor.fetchall()

            check_name = subprocess.Popen(["piston", "--node", "wss://node.steem.ws", "listaccounts"],
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE).communicate()
            check_name = ''.join(map(str, list(check_name)))

            for account in result:
                if account['accountName'] in check_name:
                    if args.verbose:
                        print("+ Found", account['accountName'])
                else:
                    if args.verbose:
                        print("- Missing", account['accountName'])
                    if not args.mock:
                        cursor.execute("UPDATE `SteemAccounts` SET `isActive`=0, `isPending`=0, `hasError`=1 WHERE `accountName`='" + str(account['accountName']) + "'")

    finally:
        connection.close()
