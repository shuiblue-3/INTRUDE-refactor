#
#
# INTERFACE.PY
#
# An interface webpage for viewing potentially redundant pairs of GitHub pull request & for sending
# out comments to them. Interacts with a MySQL database called duppr_pair, which is structured with
# the following columns and values:
#       0: id - a unique key for each pair of PRs
#       1: repo - the name of the repository the PRs are contained within
#       2: pr1 - the number of the primary repository
#       3: pr2 - the number of the secondary repository
#       4: score - the similarity score of the pair
#       5-14: {feature scores of the pair}
#       15: comment_sent - records if a comment has been sent to this pair (1), if it has not yet
#           been sent (0), or if this pair has been added to the 'do not send' list (-1)
#       16: notes - a blob for storing any notes that the users of this webpage may want to record
#       17-19: {not currently in use}
#       20: toppair - (0) if the pair is marked as 'not a top pair' (default)
#                     (1) if the pair is the most recent pair from its repo, or if a comment has been
#                         sent to this pair
#                     (-1) if the pair has been manually chosen as top pair
#                     (2) if a comment has been sent to another pair from the current pair's repo
#       21: timestamp - the timestamp of the most recent pr in the pair. Format: yyyy-mm-ddThh:ee:ssZ
#           where y is year, m is month, d is day, h is hour (24-hr), e is minute, and s is second
# This page, using the 'update' button, pulls .txt tab-separated files from a local file to fill in
# PR pair entries to the database. It uses Flask to connect to the database and render its entries.
# It also uses PRcommenter.py to send out comments to the pull requests listed.
#
#

from flask import Flask, redirect, request, render_template
from datetime import datetime, timedelta
import mysql.connector
import csv
import os
import platform
# import PRcommenter
import github.github_api
import init

# api = scraper.GitHubAPI()
from admin import PRcommenter

pr2_created_at_index = 2
##### feature list 33 in total ########
similarity_final = 4
title_lsi = 5
title_tfidf = 6
body_lsi = 7
body_tfidf = 8
commit_lsi = 9
commit_tfidf = 10
pr1_add_files = 11
pr2_add_files = 12
pr1_delete_files = 13
pr2_delete_files = 14
add_files_sim = 15
delet_files_sim = 16
add_filenames_sim = 17
delet_filenames_sim = 18
code_sim_addCode_lsi = 19
code_sim_addCode_lsi_overlap_filepath = 20
code_sim_addCode_lsi_same_filename = 21
code_sim_addCode_tfidf_add = 22
code_sim_addCode_tfidf_overlap_filepath = 23
code_sim_addCode_tfidf_same_filename = 24
code_sim_deleteCode_lsi = 25
code_sim_deleteCode_lsi_overlap_filepath = 26
code_sim_deleteCodelsi_same_filename = 27
code_sim_deleteCode_tfidf_add = 28
code_sim_deleteCode_tfidf_overlap_filepath = 29
code_sim_deleteCodetfidf_same_filename = 30
location_similarity_allfile = 31
location_similarity_overlapfile = 32
timeInterval = 33
ref_version = 34
ref_issue = 35
ref_SHA = 36
ref_url = 37
#############

api = github.github_api.GitHubAPI()
app = Flask(__name__)
htmlpage_url = 'interface.html'

# Connect to MySQL database
# with open('./input/mysqlParams.txt') as f:
with open(init.mysqlParam) as f:
    MYSQL_USER, MYSQL_PASS, MYSQL_HOST, PORT = f.read().splitlines()
# conn = mysql.connector.connect(user=MYSQL_USER, password=MYSQL_PASS, host=MYSQL_HOST, database='repolist', port='3306')
conn = mysql.connector.connect(user=MYSQL_USER, password=MYSQL_PASS, host=MYSQL_HOST, database='fork', port=PORT)
cur = conn.cursor()
# Create flag for showing all PR pairs vs one per repo
show_hide = 'hide'


# Updates database by parsing files
# Removes pairs if they're 2+ days old



# Switches between show and hide mode
# Show: all pairs visible. Hide: only one pair per repo visible.

# @app.route('/show-hide', methods=['POST'])
# def show_hide_switch():
#     global show_hide
#     show_hide = request.form['show_hide_button']  # check whether user clicked "show" button or "hide" button
#     return load_home()


# Sets toppair value
# Arguments: value, the value to set toppair to
#            pair_id, the id of the pair whose value we're changing

@app.route('/set-toppair')
def set_toppair(value, pair_id):
    # sql_str = "UPDATE duppr_pair SET toppair=%s WHERE id=%s" % (value, pair_id,)
    sql_str = "UPDATE duppr_pair_update SET toppair=%s WHERE id=%s" % (value, pair_id,)
    # print(sql_str)
    cur.execute(sql_str)
    conn.commit()
    return


# Runs upon user clicking "Choose this [pair] instead".
# Manually sets the given pair (identified by id returned by 'move' form request) as the top pair for its repo.
# This entails setting its toppair value to -1, and that of all others within its repo to 0.

@app.route('/change-top-pair', methods=['POST'])
def change_toppair():
    pair_id = request.form['move']  # get id of the pair in question
    set_toppair(-1, pair_id)  # set its toppair value to -1
    # cur.execute("SELECT * FROM duppr_pair WHERE id=%s", (pair_id,))  # get the entire row corresponding to this pair
    cur.execute("SELECT * FROM duppr_pair_update WHERE id=%s",
                (pair_id,))  # get the entire row corresponding to this pair
    row = cur.fetchall()
    cur.execute("SELECT * FROM duppr_pair_update")  # get all rows from the db
    # cur.execute("SELECT * FROM duppr_pair")  # get all rows from the db
    data = cur.fetchall()
    for row_check in data:  # look at each row in the database
        if (row[0][0] != row_check[0]) & (row[0][1] == row_check[
            1]):  # if the current row is not the original row, but if they are from the same repo
            set_toppair(0, row_check[0])  # set the current row's toppair value to -1
    # save changes and reload page
    conn.commit()
    return load_home()


# Runs when the notes 'save' button is clicked; edits notes column in database.

@app.route('/notes', methods=['POST'])
def notes():
    note = request.form['notebox']  # get notes from textarea in html
    repo_id = request.form['save_button']  # get repo name
    # update_sql = "UPDATE duppr_pair SET notes= \'%s\' WHERE id=%s" % (note, repo_id)
    update_sql = "UPDATE duppr_pair_update SET notes= \'%s\' WHERE id=%s" % (note, repo_id)
    # print(update_sql)
    cur.execute(update_sql)  # save notes to db
    conn.commit()  # save changes
    return load_home()


# Finds & marks the 'top pair' (most recent) in each repository
# Edits toppair column in database.
# Called during loading of homepage.

@app.route('/top-pair')
def top_pair_featureBiggerThanDotEight():
    # sql_str = "SELECT * \
    #         FROM duppr_pair a\
    #         WHERE a.repo COLLATE utf8mb4_unicode_ci NOT IN  (SELECT DISTINCT b.repo FROM dupPR_repo b)\
    #               AND  (score > 0.8 OR title > 0.8 OR description > 0.8 OR patch_content > 0.8 OR patch_content_overlap > 0.8 \
    #    or changed_file>0.8 or changed_file_overlap >0.8 or location > 0.8 or location_overlap>0.8 or issue_number = 1 )\
    #               AND (notes NOT LIKE '%FP%' OR notes NOT LIKE '%doc%' OR notes IS NULL)\
    #               AND TIMESTAMPDIFF(DAY, `timestamp`, CURRENT_TIMESTAMP()) <= 2\
    #         ORDER BY timestamp DESC;"
    sql_str = "SELECT * \
            FROM duppr_pair_update a\
            WHERE a.repo COLLATE utf8mb4_unicode_ci NOT IN  (SELECT DISTINCT b.repo FROM dupPR_repo b)\
                  AND  (score >0.8 or title_lsi >0.8 or title_tfidf >0.8 or body_lsi >0.8 or body_tfidf >0.8 or \
                  commit_lsi >0.8 or commit_tfidf >0.8 or add_files_sim >0.8 or delet_files_sim >0.8 or \
                  add_filenames_sim >0.8 or delet_filenames_sim >0.8 or code_sim_addCode_lsi >0.8 or \
                  code_sim_addCode_lsi_overlap_filepath >0.8 or code_sim_addCode_lsi_same_filename >0.8 or \
                  code_sim_addCode_tfidf_add >0.8 or code_sim_addCode_tfidf_overlap_filepath >0.8 or \
                  code_sim_addCode_tfidf_same_filename >0.8 or code_sim_deleteCode_lsi >0.8 or \
                  code_sim_deleteCode_lsi_overlap_filepath >0.8 or code_sim_deleteCodelsi_same_filename >0.8 or \
                  code_sim_deleteCode_tfidf_add >0.8 or code_sim_deleteCode_tfidf_overlap_filepath >0.8 or \
                  code_sim_deleteCodetfidf_same_filename >0.8 or location_similarity_allfile >0.8 or \
                  location_similarity_overlapfile >0.8 or ref_version =1 or ref_issue =1 or ref_SHA =1 or ref_url =1  )\
                  AND (notes NOT LIKE '%FP%' OR notes NOT LIKE '%doc%' OR notes IS NULL)\
                  AND TIMESTAMPDIFF(DAY, `timestamp`, CURRENT_TIMESTAMP()) <= 2\
            ORDER BY timestamp DESC;"
    cur.execute(sql_str)
    data_sorted = cur.fetchall()
    conn.commit()  # save changes
    # print(str(len(data_sorted)))
    return data_sorted  # return the sorted list of all pairs@app.route('/top-pair')


def top_pair_similarityBiggerThanThreshold_filterOverlapParticipant(threshold,numOverlapParticipants):
    sql_str = "SELECT * \
               FROM duppr_pair_update a\
               WHERE a.repo COLLATE utf8mb4_unicode_ci NOT IN  (SELECT DISTINCT b.repo FROM dupPR_repo b)\
                     AND  (score >" + threshold + ")\
                     AND (notes NOT LIKE '%FP%' OR notes NOT LIKE '%doc%' OR notes IS NULL)\
                     AND TIMESTAMPDIFF(DAY, `timestamp`, CURRENT_TIMESTAMP()) <= 2\
                     AND num_overlapped_participants <= "+numOverlapParticipants+"\
               ORDER BY timestamp DESC;"
    cur.execute(sql_str)
    data_sorted = cur.fetchall()
    conn.commit()  # save changes
    # print(str(len(data_sorted)))
    return data_sorted  # return the sorted list of all pairs


@app.route('/findRepo', methods=['POST'])
def findRepo():
    repo = request.form['repo']
    sql_str = "SELECT * \
                  FROM duppr_pair_update \
                  WHERE repo = '"+ repo+ "\'\
                  ORDER BY timestamp DESC;"
    print(sql_str)
    cur.execute(sql_str)
    data_sorted = cur.fetchall()
    conn.commit()  # save changes
    return render_template(htmlpage_url, id="home", data_dups=data_sorted)




@app.route('/filterOverlapParticipants', methods=['POST'])
def filterOverlapParticipants():
    numOverlapParticipants = request.form['numOverlapParticipants']
    threshold = request.form['threshold']
    data_sorted = top_pair_similarityBiggerThanThreshold_filterOverlapParticipant(threshold, numOverlapParticipants)
    return render_template(htmlpage_url, id="home", data_dups=data_sorted)



# Runs upon clicking 'send comment.' Edits comment_sent col in db.

@app.route('/home-sc', methods=['POST'])
def send_comment():
    comments_body = request.form['comments']
    pair_id = request.form['send_comment_button']  # get row id (in db) from value of send_comment_button button
    cur.execute("SELECT * FROM duppr_pair_update WHERE id=%s", (pair_id,))  # get info about pr pair
    # cur.execute("SELECT * FROM duppr_pair WHERE id=%s", (pair_id,))  # get info about pr pair
    pr_info = cur.fetchall()
    pr = int(pr_info[0][2], 10)  # get pr number, type as int
    pr2 = int(pr_info[0][3], 10)  # get number of corresponding pr, type as int
    repo = pr_info[0][1]  # get repo name
    # PRcommenter.make_github_comment(repo, pr, pr2, "")  # send comment
    comment_sent_result = PRcommenter.make_github_comment(repo, pr, pr2, comments_body)  # send comment
    if (comment_sent_result == "success"):
        # update duppr_pair row
        cur.execute("UPDATE duppr_pair_update SET comment_sent=1 WHERE id=%s",
                    # cur.execute("UPDATE duppr_pair SET comment_sent=1 WHERE id=%s",
                    (pair_id,))  # change comment_sent value to 1 -- flags as sent
        conn.commit()  # save changes
        # print(cur.rowcount,
        #       "rows updated in duppr_pair")  # terminal notification to inform how many rows (pairs) have been altered

        # insert repo into duppr_repo
        insert_sql = "insert into dupPR_repo (repo, pr1, pr2) values (%s , %s , %s)"
        # print(insert_sql)
        cur.execute(insert_sql, (repo, pr, pr2))
        conn.commit()  # save changes
        print(cur.rowcount,
              "rows updated to dupPR_repo")  # terminal notification to inform how many rows (pairs) have been altered


    else:
        print("database not update, because comment sent failed.")

    load_home()  # reload page. FYI: not sure why two load_homes are required, but they seem to be.
    return load_home()


# Runs upon clicking 'don't send comment.' Edits comment_sent col in db.
# Adds repo (on home page) to rejects page/list.

@app.route('/home-no-sc', methods=['POST'])
def no_send_comment():
    pair_id = request.form['no_send_comment_button']  # get row id (in db) from value of no_send_comment_button button
    # cur.execute("UPDATE duppr_pair SET comment_sent=-1 WHERE id=%s",
    cur.execute("UPDATE duppr_pair_update SET comment_sent=-1 WHERE id=%s",
                (pair_id,))  # change comment_sent value to -1 (flags for moving to another list)
    conn.commit()  # save changes
    print(cur.rowcount, "rows updated.")  # terminal notification to inform how many rows (pairs) have been altered
    load_home()
    return load_home()


# Runs upon clicking 'reset.' Edits comment_sent col in db.
# Adds repo (on rejects page) back to home page.

# @app.route('/rejects-reset-sc', methods=['POST'])
# def reset_send_comment():
#     pair_id = request.form['reset_button']  # get row id (in db) from value of reset_button button
#     cur.execute("UPDATE duppr_pair SET comment_sent=0 WHERE id=%s",
#                 (pair_id,))  # change comment_sent value to 0 (flags for returning to main list)
#     conn.commit()  # save changes
#     print(cur.rowcount, "rows updated.")  # terminal notification to inform how many rows (pairs) have been altered
#     return load_reject_page()


# Render homepage
# Lists:
#   data[] - top pairs to be displayed in the homepage
#   data_dups[] - non-top pairs to be displayed in the homepage (if the show_hide switch is on "show")
#   data_init[] - all pairs


@app.route('/getPRFeatureBiggerThanDotEight', methods=['POST'])
def getPRFeatureBiggerThanDotEight():
    data = []
    data_dups = top_pair_featureBiggerThanDotEight()
    return render_template(htmlpage_url, data=data, id="home", data_dups=data_dups)


@app.route('/updatePRstate', methods=['POST'])
def updatePRstate():
    data = []
    data_dups_update = []
    data_dups = top_pair_featureBiggerThanDotEight()
    for line in data_dups:
        repo, pr1, pr2 = line[1:4]

        # ###  ###  ###  ### get PR state
        pr1_status = api.pr_status(repo, pr1)
        pr2_status = api.pr_status(repo, pr2)

        # ###  ###  ###  ### get PR timeline
        pr1_events = api.get_issue_pr_timeline(repo, pr1)
        pr2_events = api.get_issue_pr_timeline(repo, pr2)
        pr1_participant_list, pr1_num_comments = analyzePREvents(pr1_events)
        pr2_participant_list, pr2_num_comments = analyzePREvents(pr2_events)
        num_participants_overlap = len(pr1_participant_list.intersection(pr2_participant_list))

        # update to db
        update_pr_state_db(repo, pr1, pr2, pr1_status, pr2_status, len(pr1_participant_list), len(pr2_participant_list),
                           pr1_num_comments, pr2_num_comments, num_participants_overlap)

        # update tuple
        lst = list(line)
        lst[22] = pr1_status
        lst[23] = pr2_status
        lst[24] = pr1_num_comments
        lst[25] = pr2_num_comments
        lst[26] = len(pr1_participant_list)
        lst[27] = len(pr2_participant_list)
        lst[28] = num_participants_overlap

        newline = tuple(lst)
        data_dups_update.append(newline)

    return render_template(htmlpage_url, data=data, id="home", data_dups=data_dups_update)


def analyzePREvents(PR_events):
    participant_list = []
    comment_count = 0
    isMerged = False
    closed_at = ''
    for event in PR_events:
        keys = event.keys()
        if 'author' in keys:
            participant_list.append(event['author']['name'])
        if 'committer' in keys:
            participant_list.append(event['committer']['name'])
        if 'actor' in keys:
            if (event['actor'] is not None) \
                    and ('bot' not in event['actor']['login']) and ('codecov' not in event['actor']['login']):
                participant_list.append(event['actor']['login'])
        if 'user' in keys:
            if (event['user'] is not None) and ('bot' not in event['user']['login']) and ('codecov' not in event['user']['login']):
                participant_list.append(event['user']['login'])
        if event['event'] == 'commented':
            comment_count += 1
        if event['event'] == 'merged':
            isMerged = True
        if event['event'] == 'closed':
            closed_at = event['created_at']
    if 'GitHub' in participant_list:
        participant_list.remove('GitHub')
    # print(str(len(set(participant_list))) + " participants " + str(comment_count) + " comments")
    return set(participant_list), comment_count, isMerged, closed_at


@app.route('/')
def load_home():
    data = []
    data_dups = top_pair_similarityBiggerThanThreshold_filterOverlapParticipant('0.9','0')
    return render_template(htmlpage_url, data=data, id="home", data_dups=data_dups)


def update_pr_state_db(repo, pr1, pr2, pr1_status, pr2_status, pr1_participant_num, pr2_participant_num,
                       pr1_num_comments, pr2_num_comments, num_participants_overlap,pr1_closed_at, pr2_closed_at):
    # sql_str = "update duppr_pair " \
    sql_str = "update duppr_pair_update " \
              "set pr1_state = %s, pr2_state = %s, " \
              "    num_pr1_participants= %s,num_pr2_participants = %s ," \
              "    num_pr1_comments = %s,num_pr2_comments = %s ," \
              "    num_overlapped_participants = %s ," \
              "    pr1_closed_at = %s ," \
              "    pr2_closed_at = %s " \
              "WHERE repo = %s and pr1 =%s and pr2 =%s ;"

    cur.execute(sql_str, (
        pr1_status, pr2_status, pr1_participant_num, pr2_participant_num, pr1_num_comments, pr2_num_comments,
        num_participants_overlap, pr1_closed_at,pr2_closed_at, repo, pr1, pr2))
    conn.commit()  # save changes
    # print("update %s pr status %s %s  %s %s " % (repo, pr1, pr2, pr1_status, pr2_status))


# Render page with rejected PR pairs
# Lists:
#   data[] - rejected pairs, to be displayed on this page
#   data_init[] - all pairs

# @app.route('/rejects')
# def load_reject_page():
#     cur.execute("SELECT * FROM duppr_pair")  # get all pr pairs from the db
#     data_init = cur.fetchall()
#     data = []
#     for row in data_init:  # loop through pr pairs (rows)
#         if row[15] == -1:  # only display repos for which we've clicked "don't send comment"
#             data.append(row)
#     return render_template('interface.html', data=data, id="rejects", data_dups=[])


if __name__ == '__main__':
    app.run(debug=True,
            # host='128.2.112.25')  # in order to be accessed from remote : https://askubuntu.com/questions/224392/how-to-allow-remote-connections-to-flask/224396
            host='0.0.0.0')  # in order to be accessed from remote : https://askubuntu.com/questions/224392/how-to-allow-remote-connections-to-flask/224396
