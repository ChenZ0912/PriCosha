#Import Flask Library
from flask import Flask, render_template, request, session, url_for, redirect
import pymysql.cursors
import json

#Initialize the app from Flask
app = Flask(__name__)

#Configure MySQL
conn = pymysql.connect(host='localhost',
                       port = 8889,
                       user='root',
                       password='root',
                       db='PriCoSha',
                       charset='utf8mb4',
                       cursorclass=pymysql.cursors.DictCursor)
#
#Define a route to hello function
@app.route('/')
def hello():
    return render_template('login.html')
    
#
#Define route for login
@app.route('/login')
def login():
    return render_template('login.html')

#Define route for register
@app.route('/register')
def register():
    return render_template('register.html')

#Authenticates the login
@app.route('/loginAuth', methods=['GET', 'POST'])
def loginAuth():
    #grabs information from the forms
    email = request.form['email']
    password = request.form['password']

    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM person WHERE email = %s and password = SHA2(%s, 256)'
    cursor.execute(query, (email, password))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    cursor.close()
    error = None

    if(data):
        #creates a session for the the user
        #session is a built in
        session['email'] = email
        session['fname'] = data['fname']
        session['lname'] = data['lname']
        return redirect(url_for('home'))
    else:
        #returns an error message to the html page
        error = 'Invalid login or email'
        return render_template('login.html', error=error)

#Authenticates the register
@app.route('/registerAuth', methods=['GET', 'POST'])
def registerAuth():
    #grabs information from the forms
    email = request.form['email']
    password = request.form['password']
    fname = request.form['fname']
    lname = request.form['lname']

    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM person WHERE email = %s'
    cursor.execute(query, (email))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    error = None

    if(data):
        #If the previous query returns data, then user exists
        error = "This person already exists"
        return render_template('register.html', error = error)
    else:
        ins = 'INSERT INTO person VALUES(%s, SHA2(%s, 256), %s, %s)'
        cursor.execute(ins, (email, password, fname, lname))
        conn.commit()
        cursor.close()
        return render_template('index.html')


@app.route('/home')
def home():
    person = session['email']
    fname = session['fname']
    lname = session['lname']
    cursor = conn.cursor()

    try:
        createGroup_message = request.args.get("createGroup_message")
    except:
        createGroup_message = ""
    try:
        addFriend_message = request.args.get("addFriend_message")
    except:
        addFriend_message = ""
    try:
        candidate_usrs = json.loads(request.args.get("candidate_usrs"))
    except:
        candidate_usrs = ""

    query = 'SELECT * FROM ContentItem WHERE email_post = %s ORDER BY post_time DESC'
    cursor.execute(query, (person))
    data = cursor.fetchall()

    query = """
                SELECT *
                FROM Friendgroup
                WHERE owner_email = %s
        """
    cursor.execute(query, (person))
    group_data = cursor.fetchall()

    query = '''
            SELECT owner_email, fg_name
            FROM Belong
            WHERE email = %s
    '''
    cursor.execute(query, (person))
    joined_groups = cursor.fetchall()
    
    query ='''
        SELECT item_id, tagtime, email_tagger, email_post, post_time, item_name
        FROM Tag NATURAL JOIN ContentItem
        WHERE email_tagged = %s AND status = False
    '''
    
    cursor.execute(query, (person))
    tags = cursor.fetchall()
    
    cursor.close()
    return render_template('home.html', person=person, fname = fname, lname = lname, posts=data, groups = group_data,
                           joined_groups = joined_groups, createGroup_message = createGroup_message,
                           addFriend_message = addFriend_message, candidate_usrs = candidate_usrs, tags = tags)


@app.route('/post', methods=['GET', 'POST'])
def post():
    email = session['email']
    item_name = request.form['item_name']
    file_path = request.form['file_path']
    is_pub = request.form['is_pub']
    cursor = conn.cursor()
    query = '''INSERT INTO ContentItem (email_post, post_time, file_path, item_name, is_pub) 
               VALUES (%s, CURRENT_TIMESTAMP(), %s, %s, %s)'''
    try:
        cursor.execute(query, (email, file_path, item_name, is_pub))

    except:
        conn.rollback()

    query_getID = '''
                SELECT item_id
                FROM ContentItem
                WHERE email_post = %s AND file_path = %s AND item_name = %s AND is_pub = %s
                AND post_time = (
                    SELECT MAX(post_time)
                    FROM ContentItem
                    WHERE email_post = %s AND file_path = %s AND item_name = %s AND is_pub = %s
                )
            '''
    cursor.execute(query_getID, (email, file_path, item_name, is_pub, email, file_path, item_name, is_pub))
    itID = cursor.fetchone()



    if is_pub == '0':
        fg = request.form.getlist('fgSharedWith')
        ins = '''
           INSERT INTO Share (owner_email, fg_name, item_id) VALUES (%s, %s, %s)
           '''
        for fg_name in fg:
            cursor.execute(ins, (email, fg_name, itID['item_id']))
    conn.commit()
    cursor.close()
    return redirect(url_for('home'))

#If form createGroup in "home.html" is submitted, this function will be called
@app.route('/createGroup', methods = ['GET', 'POST'])
def createGroup():
    email = session['email']
    fg_name = request.form['fg_name']
    description = request.form['description']
    cursor = conn.cursor()
    query = """
            SELECT *
            FROM FriendGroup
            WHERE owner_email = %s AND fg_name = %s
    """
    cursor.execute(query, (email, fg_name))
    data = cursor.fetchall()
    # Check whether this group has been created, and pass the message back to home()
    if data:
        return redirect(url_for('home', createGroup_message = fg_name + " has already been created. Please use a different group name"))
    else:
        # Insert the group into FriendGroup
        query = """
                INSERT INTO FriendGroup (owner_email, fg_name, description)
                VALUES (%s, %s, %s)
        """
        cursor.execute(query, (email, fg_name, description))
        conn.commit()

        # Add the owner to the Belong
        query = """
            INSERT INTO Belong (email, owner_email, fg_name) VALUES (%s, %s, %s)
        """
        cursor.execute(query, (email, email, fg_name))
        conn.commit()
        return redirect(url_for('home', createGroup_message = "Successfully created group {}!".format(fg_name)))
    cursor.close()

@app.route('/searchUsr', methods = ['GET', 'POST'])
def searchUsr():
    toSearch_fname = request.form['fname']
    toSearch_lname = request.form['lname']

    cursor = conn.cursor()
    query = """
        SELECT email
        FROM Person
        WHERE fname = %s AND lname = %s
    """

    cursor.execute(query, (toSearch_fname, toSearch_lname))
    data = cursor.fetchall()
    cursor.close()
    if data:
        return redirect(url_for('home', candidate_usrs = json.dumps(data)))
    else:
        return redirect(url_for('home', addFriend_message =
        "Can't find {} {}, please confirm the name of the person you are adding".format(toSearch_fname, toSearch_lname)))

@app.route('/addFriend', methods = ['GET', 'POST'])
def addFriend():
    if request.form['submit_button'] == "Cancel":
        return redirect(url_for('home'))

    elif request.form['submit_button'] == "Add":
        owner_email = session['email']
        fg_name = request.form['fg_name']
        toAdd_email = request.form['usr']
        cursor = conn.cursor()

        query = """
                SELECT *
                FROM belong 
                WHERE email = %s AND owner_email = %s AND fg_name = %s
        """
        cursor.execute(query, (toAdd_email, owner_email, fg_name))
        exists = cursor.fetchone()
        if exists:
            cursor.close()
            return redirect(url_for('home', addFriend_message =
            "{} already exists in friend group {}".format(toAdd_email, fg_name)))
        else:
            query = """
                  INSERT INTO Belong (email, owner_email, fg_name) VALUES (%s, %s, %s)
            """
            cursor.execute(query, (toAdd_email, owner_email, fg_name))
            conn.commit()
            cursor.close()
            return redirect(url_for('home', addFriend_message =
            "{} successfully added to friend group {}".format(toAdd_email, fg_name)))

    # query = """
    #     SELECT *
    #     FROM Belong
    #     WHERE owner_email = %s AND email = %s AND fg_name = %s
    # """
    # cursor.execute(query, (owner_email, email, fg_name))
    # data = cursor.fetchall()
    # if not data:
    #     query = """
    #         INSERT INTO Belong (email, owner_email, fg_name) VALUES (%s, %s, %s)
    #     """
    #     cursor.execute(query, (email, owner_email, fg_name))
    #     conn.commit()

# @app.route('/select_blogger')
# def select_blogger():
#     #check that user is logged in
#     #username = session['username']
#     #should throw exception if username not found
#
#     cursor = conn.cursor();
#     query = 'SELECT DISTINCT email FROM ContentItem'
#     cursor.execute(query)
#     data = cursor.fetchall()
#     cursor.close()
#     return render_template('select_blogger.html', user_list=data)
#
# @app.route('/show_posts', methods=["GET", "POST"])
    
#def show_posts():
#    poster = request.args['poster']
#    cursor = conn.cursor();
#    query = 'SELECT ts, blog_post FROM blog WHERE username = %s ORDER BY ts DESC'
#    cursor.execute(query, poster)
#    data = cursor.fetchall()
#    cursor.close()
#    return render_template('show_posts.html', poster_name=poster, posts=data)
    
@app.route('/browse')
def browse():
    try:
        message = request.args["message"]
    except:
        message = ""

    cursor = conn.cursor()
    query = '''SELECT * 
                    FROM ContentItem
                    WHERE (is_pub = 1 OR 
                        item_id IN (
                                SELECT item_id
                                FROM Belong NATURAL JOIN Share
                                WHERE email = %s
                        )
                    )
                    AND post_time > TIMESTAMPADD(DAY, -1, CURRENT_TIMESTAMP())
                    ORDER BY post_time DESC'''
    cursor.execute(query, (session['email']))
    data = cursor.fetchall()
    cursor.close()
    return redirect(url_for('home', posts = data, message = message))

@app.route('/tag', methods = ["POST"])
def tag():
    if request.form['submit_button'] == "Tag":
        tagger_email = session['email']
        item_id = request.form['item_id']
        tagged_email = request.form['taggedEmail']
        cursor = conn.cursor()

        query = '''
            SELECT * FROM Person WHERE email = %s
        '''
        cursor.execute(query, (tagged_email))
        data = cursor.fetchone()
        # edge case: tagged_email not registered
        if not data:
            return(redirect(url_for('browse', message=
            "Tagging failed, {} is not a valid registered user".format(tagged_email))))

        query = '''
            SELECT item_id 
            FROM ContentItem 
            WHERE is_pub = 1 
            UNION 
            SELECT item_id
            FROM Share NATURAL JOIN Belong 
            WHERE email = %s AND item_id = %s
        '''
        cursor.execute(query, (tagged_email, item_id))
        data = cursor.fetchall()
        #edge case: tagged_email doesn't have access to the post
        if not data:
            return(redirect(url_for('browse', message =
            "Tagging failed, {} has no access to post {}".format(tagged_email, item_id))))
        else:
            #egde case: user already tagged
            query = ''' 
                SELECT * 
                FROM Tag 
                WHERE email_tagged = %s AND email_tagger = %s AND item_id = %s
            '''
            cursor.execute(query, (tagged_email, tagger_email, item_id))
            data = cursor.fetchall()
            if data:
                return (redirect(url_for('browse', message=
                "Tagging failed, {} has already been tagged to post {}".format(tagged_email, item_id))))

            query = '''
                INSERT INTO `Tag`(`email_tagged`, `email_tagger`, `item_id`, `status`, `tagtime`) 
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP())
            '''

            #checks if self-tagging
            if tagged_email == tagger_email:
                cursor.execute(query, (tagged_email, tagger_email, item_id, True))
            else:
                cursor.execute(query, (tagged_email, tagger_email, item_id, False))
            conn.commit()
            cursor.close()
            return(redirect(url_for('browse', message=
            "tag request successfully sent to {}".format(tagged_email))))

@app.route('/ManageTag', methods = ['GET', 'POST'])
def ManageTag():
#    email_tagged = request.form['email_tagged']
    email_tagged = session['email']
    email_tagger = request.form['email_tagger']
    item_id = request.form['item_id']
    status = request.form['status']
    
    cursor = conn.cursor()
    
    if status == '1': #accept the request, update Dadabase status to True. 需要更新 home
        query = """
        UPDATE Tag 
        SET status = True 
        WHERE email_tagged = %s and email_tagger = %s and item_id = %s"""
        
        cursor.execute(query, (email_tagged, email_tagger, item_id))
        conn.commit()
        
        
    elif status == '0': #reject the request, delete tag from Tag table
        query = "DELETE FROM Tag WHERE email_tagged = %s and email_tagger = %s and item_id = %s"
        cursor.execute(query, (email_tagged, email_tagger, item_id))
        conn.commit()

    
    cursor.close()
    return redirect(url_for('home') )

@app.route('/rate', methods = ["POST"])
def rate():
    if request.form['submit_button'] == "Rate":
        email = session['email']
        item_id = request.form['item_id']
        emoji = request.form['emoji']
        cursor = conn.cursor()

        query = """
            SELECT * FROM Rate WHERE email = %s AND item_id = %s
        """
        cursor.execute(query, (email, item_id))
        data = cursor.fetchone()
        if data:

            query = """
            UPDATE `Rate` SET `rate_time` = CURRENT_TIMESTAMP(),`emoji`= %s WHERE 
            `email` = %s AND `item_id` = %s
            """
            cursor.execute(query, (emoji, email, item_id))
            conn.commit()
            cursor.close()
            return (redirect(url_for('browse', message="Rating successfully modified!")))
        else:
            query = """
            INSERT INTO `Rate`(`email`, `item_id`, `rate_time`, `emoji`) 
            VALUES (%s, %s, CURRENT_TIMESTAMP(), %s)
            """
            cursor.execute(query, (email, item_id, emoji))
            conn.commit()
            cursor.close()
            return (redirect(url_for('browse', message="Successfully rated!")))

    return (redirect(url_for('browse')))


@app.route('/logout')
def logout():
    session.pop('email')
    return redirect('/')
#
app.secret_key = 'some key that you will never guess'
#Run the app on localhost port 5000
#debug = True -> you don't have to restart flask
#for changes to go through, TURN OFF FOR PRODUCTION
if __name__ == "__main__":
    app.run('127.0.0.1', 5000, debug = True)
