#!/usr/bin/python3

import os
import time
import subprocess
import pymysql.cursors

os.environ['PATH'] += "******************"
os.environ['UNLOCK'] = "******************"


def check_name_added(this_account):
    check_name = subprocess.Popen(["piston", "--node", "wss://node.steem.ws", "balance", account['accountName']],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE).communicate()
    check_name = ''.join(map(str, list(check_name)))
    if 'piston.steem.AccountDoesNotExistsException' in check_name:
        cursor.execute("DELETE FROM `SteemAccounts` WHERE `id`=" + str(this_account['id']))
        cursor.execute(
            """INSERT INTO Notifications (userID, title, text, dateTime) VALUES
            ({0}, '{1} Account Error', 'Account error, information not accurate.',
            FROM_UNIXTIME({2}))""".format(
                str(account['userID']), str(this_account['accountName']), str(time.time())))
        return False
    elif account['accountName'] in check_name:
        cursor.execute(
            "UPDATE `SteemAccounts` SET `isActive`=1, `isPending`=0 WHERE `id`=" + str(this_account['id']))
        cursor.execute(
            """INSERT INTO Notifications (userID, title, text, dateTime) VALUES
            ({0}, '{1} Added', 'Account added and ready for voting rules.',
            FROM_UNIXTIME({2}))""".format(
                str(account['userID']), str(this_account['accountName']), str(time.time())))
        return True
    else:
        cursor.execute("DELETE FROM `SteemAccounts` WHERE `id`=" + str(this_account['id']))
        cursor.execute(
            """INSERT INTO Notifications (userID, title, text, dateTime) VALUES
            ({0}, '{1} Account Error', 'Account error, information not accurate.',
            FROM_UNIXTIME({2}))""".format(
                str(account['userID']), str(this_account['accountName']), str(time.time())))
        return False


if __name__ == '__main__':
    connection = pymysql.connect(host='******************',
                                 user='******************',
                                 password='******************',
                                 db='******************',
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM `SteemAccounts` WHERE `isPending`=1")
            result = cursor.fetchall()
            for account in result:
                output = subprocess.Popen(["piston", "--node", "wss://node.steem.ws", "addkey",
                                           account['AccountKey']],
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE).communicate()
                output = ''.join(map(str, list(output)))
                if 'Key already in storage' in output:
                    check_name_added(account)
                elif 'Error' in output:
                    cursor.execute("DELETE FROM `SteemAccounts` WHERE `id`=" + str(account['id']))
                    cursor.execute(
                        """INSERT INTO Notifications (userID, title, text, dateTime) VALUES
                        ({0}, '{1} Account Error', 'Account error, information not accurate.',
                        FROM_UNIXTIME({2}))""".format(
                            str(account['userID']), str(account['accountName']), str(time.time())))
                else:
                    check_name_added(account)

    finally:
        connection.close()
