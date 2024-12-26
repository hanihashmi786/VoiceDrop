from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from werkzeug.security import  check_password_hash


app = Flask(__name__, static_folder='assets')
app.secret_key = "your_secret_key"

# Database configuration
DB_NAME = "VoiceDrop"
DB_USER = "admin"
DB_PASSWORD = "12345"
DB_HOST = "localhost"
DB_PORT = "5432"

UPLOAD_FOLDER = 'static/uploads/'
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def connect_to_db():
    """
    Connect to the PostgreSQL database.
    """
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def insert_user(username, password, select_team, select_user):
    """
    Insert a new user into the 'users' table.
    """
    conn = connect_to_db()
    if not conn:
        print("Database connection failed")
        return False

    try:
        cursor = conn.cursor()
        insert_query = """
        INSERT INTO users (username, password, select_team, select_user)
        VALUES (%s, %s, %s, %s);
        """
        print("Executing query:", insert_query)
        print("With parameters:", (username, password, select_team, select_user))
        cursor.execute(insert_query, (username, password, select_team, select_user))
        conn.commit()
        print("User added successfully")
        return True
    except Exception as e:
        print(f"Error inserting user: {e}")
        return False
    finally:
        if conn:
            cursor.close()
            conn.close()


def role_required(roles):
    """
    Decorator to restrict access based on roles.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if 'role' not in session or session['role'].lower() not in roles:
                flash("Access denied. You do not have permission to view this page.", "danger")
                return redirect(url_for('login'))
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

@app.route('/')
def firstscreen():

    return render_template('firstscreen.html')

#Route for login page

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        print(f"Login attempt with username: {username}, password: {password}")

        conn = connect_to_db()
        if not conn:
            flash("Database connection error.", "danger")
            return redirect(url_for('login'))

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, password, select_user
                FROM users
                WHERE username = %s
            """, (username,))
            user = cursor.fetchone()
            print(f"Query result: {user}")

            if user:
                if user[2] == password:  # Plaintext password comparison
                    session['user_id'] = user[0]
                    session['username'] = user[1]
                    session['role'] = user[3]
                    flash("Login successful!", "success")

                    if user[3].lower() == 'admin':
                        print("Redirecting to dashboard...")
                        return redirect(url_for('dashboard'))
                    elif user[3].lower() == 'qa':
                        print("Redirecting to QA entries...")
                        return redirect(url_for('qaentries'))
                    elif user[3].lower() == 'user':
                        print("Redirecting to user entries...")
                        return redirect(url_for('userentries'))
                    else:
                        flash("Invalid role assigned to user.", "danger")
                else:
                    flash("Invalid username or password.", "danger")
            else:
                flash("Invalid username or password.", "danger")
        except Exception as e:
            flash(f"Error during login: {e}", "danger")
        finally:
            conn.close()

    return render_template('login.html')


@app.route('/logout')
def logout():
    """
    Log out the user and clear the session.
    """
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

# Route for dashboard page
@app.route('/dashboard')
@role_required(['admin'])
def dashboard():
    """
    Dashboard page for admin role.
    """
    return render_template('dashboard.html', current_page='dashboard')


def fetch_users(team_filter=None):
    """
    Fetch users from the database. Optionally filter by team.
    """
    conn = connect_to_db()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        if team_filter:
            query = "SELECT username, select_team FROM users WHERE select_team = %s"
            cursor.execute(query, (team_filter,))
        else:
            query = "SELECT username, select_team FROM users"
            cursor.execute(query)

        users = cursor.fetchall()
        return users
    except Exception as e:
        print(f"Error fetching users: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    """
    Route to handle editing user details.
    """
    conn = connect_to_db()
    if not conn:
        flash("Database connection error!", "danger")
        return redirect(url_for('users'))

    try:
        cursor = conn.cursor()
        if request.method == 'POST':
            # Fetch updated data from the form
            username = request.form.get('username')
            password = request.form.get('password')
            select_team = request.form.get('select_team')

            # Update user record in the database
            update_query = """
                UPDATE users
                SET username = %s, password = %s, select_team = %s
                WHERE id = %s
            """
            cursor.execute(update_query, (username, password, select_team, user_id))
            conn.commit()
            flash("User details updated successfully!", "success")
            return redirect(url_for('users'))

        # For GET requests, fetch the user's current data
        cursor.execute("SELECT id, username, password, select_team FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        # If user not found
        if not user:
            flash("User not found!", "danger")
            return redirect(url_for('users'))

        cursor.execute("SELECT team_name FROM teams")
        teams = cursor.fetchall()

        return render_template('edit_user.html', user=user, teams=teams)
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    """
    Route to handle deleting a user by their ID.
    """
    print(f"Attempting to delete user with ID: {user_id}")  # Debug

    conn = connect_to_db()
    if not conn:
        flash("Database connection error!", "danger")
        return redirect(url_for('users'))

    try:
        cursor = conn.cursor()
        delete_query = "DELETE FROM users WHERE id = %s"
        cursor.execute(delete_query, (user_id,))
        conn.commit()

        if cursor.rowcount == 0:
            print("No user deleted. User ID may not exist.")  # Debug
            flash("User not found or already deleted!", "warning")
        else:
            print(f"Deleted user with ID: {user_id}")  # Debug
            flash("User deleted successfully!", "success")
    except Exception as e:
        print(f"Error deleting user: {e}")  # Debug
        flash(f"Error deleting user: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for('users'))


@app.route('/users', methods=['GET', 'POST'])
@role_required(['admin'])
def users():
    """
    Route to handle user listing and adding.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        select_team = request.form.get('select_team')
        select_user = request.form.get('select_user')

        # Validate input fields
        if not all([username, password, select_team, select_user]):
            flash("All fields are required!", "danger")
            return redirect(url_for('users'))

        try:
            conn = connect_to_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (username, password, select_team, select_user)
                VALUES (%s, %s, %s, %s)
            """, (username, password, select_team, select_user))
            conn.commit()
            flash("User added successfully!", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")
        finally:
            conn.close()
    
    conn = connect_to_db()
    cursor = conn.cursor()
    selected_team = request.args.get('team', None)  # Get the team from query parameters


    users = []
    if selected_team:
        # Query users for the selected team
        cursor.execute("""
            SELECT id, username, password, select_team FROM users WHERE select_team = %s
        """, (selected_team,))
        users = cursor.fetchall()
    else:
        # No team selected; users list remains empty
        selected_team = None

    # Query now ensures `id` is the first field
    cursor.execute("SELECT id, username, password, select_team FROM users")
    users = cursor.fetchall()
    cursor.execute("SELECT team_name FROM teams")
    teams = cursor.fetchall()
    conn.close()
    return render_template('users.html', users=users, teams=teams, current_page='users',selected_team=selected_team)


@app.route('/edit_team/<int:team_id>', methods=['POST'])
def edit_team(team_id):
    if request.method == 'POST':
        # Get the new team name from the form
        new_team_name = request.form.get('team_name')

        # Update the team in the database
        conn = connect_to_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE teams SET team_name = %s WHERE id = %s', (new_team_name, team_id))
        conn.commit()
        cursor.close()
        conn.close()

        # Redirect back to the teams page
        return redirect(url_for('teams'))

@app.route('/delete_team/<int:team_id>', methods=['POST'])
def delete_team(team_id):
    # Connect to the database
    conn = connect_to_db()
    cursor = conn.cursor()
    
    # Delete the team from the database
    cursor.execute('DELETE FROM teams WHERE id = %s', (team_id,))
    conn.commit()
    
    # Close the connection
    cursor.close()
    conn.close()
    
    # Redirect back to the teams page
    return redirect(url_for('teams'))

# Route for teams page
@app.route('/teams', methods=['GET', 'POST'])
@role_required(['admin'])
def teams():
    """
    Handle adding and displaying teams.
    """
    conn = connect_to_db()
    if not conn:
        flash("Database connection error.", "danger")
        return render_template('teams.html', teams=[])

    if request.method == 'POST':
        # Insert team into the database
        team_name = request.form.get('team')
        if not team_name:
            flash("Team name cannot be empty!", "warning")
        else:
            try:
                cursor = conn.cursor()
                insert_query = "INSERT INTO teams (team_name) VALUES (%s)"
                cursor.execute(insert_query, (team_name,))
                conn.commit()
                flash("Team added successfully!", "success")
            except psycopg2.IntegrityError:
                flash("Team name already exists. Please use a unique name.", "warning")
                conn.rollback()
            except Exception as e:
                print(f"Error adding team: {e}")
                flash("Error adding team. Please try again.", "danger")
            finally:
                cursor.close()

    # Retrieve all teams for display
    try:
        cursor = conn.cursor()
        fetch_query = "SELECT id, team_name FROM teams"
        cursor.execute(fetch_query)
        teams = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching teams: {e}")
        flash("Error fetching teams. Please try again.", "danger")
        teams = []
    finally:
        cursor.close()
        conn.close()

    return render_template('teams.html', teams=teams)

@app.route('/add_entry', methods=['POST'])
def add_entry():
    # Get form data
    file_name = request.form.get('file_name')
    comments = request.form.get('comments', 'Label')  # Default to 'Label' if not provided
    file = request.files.get('file_path')

    # Validate input
    if not file or not file_name:
        flash('File name and file upload are required.', 'danger')
        return redirect(url_for('entriestable'))

    if not allowed_file(file.filename):
        flash(f"Invalid file type. Allowed types are: {', '.join(ALLOWED_EXTENSIONS)}", 'danger')
        return redirect(url_for('entriestable'))

    try:
        # Save file to the uploads folder
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Connect to the database
        conn = connect_to_db()
        if conn is None:
            flash('Could not connect to the database.', 'danger')
            return redirect(url_for('entriestable'))

        cursor = conn.cursor()

        # Insert entry into the database
        query = """
            INSERT INTO audio_files (file_name, file_path, comments, date, status)
            VALUES (%s, %s, %s, %s, %s)
        """
        values = (filename, file_path, comments, datetime.now(), 'Start')

        cursor.execute(query, values)
        conn.commit()

        flash('Entry added successfully!', 'success')
    except Exception as e:
        if conn:
            conn.rollback()
        flash(f'An error occurred: {str(e)}', 'danger')
    finally:
        if conn:
            cursor.close()
            conn.close()

    return redirect(url_for('entriestable'))

@app.route('/entries', methods=['GET', 'POST'])
@role_required(['admin'])
def entries():
    if request.method == 'POST':
        user_id = request.form['user']
        comments = 'Label'  # Default comment value
        status = 'Start'    # Default status value
        
        file = request.files['audio_file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Save the file to the path
            file.save(file_path)

            # Insert into the database without status and comments from the form
            conn = connect_to_db()
            if conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO audio_files (file_name, file_path, comments, status, user_id)
                    VALUES (%s, %s, %s, %s, %s)
                """, (filename, file_path, comments, status, user_id))
                conn.commit()
                cursor.close()
                conn.close()
                flash('Entry added successfully!', 'success')
            else:
                flash('Error connecting to the database.', 'danger')
        else:
            flash('Invalid file type. Only mp3, wav, and ogg are allowed.', 'danger')

        return redirect(url_for('entries'))

    # Retrieve users for the dropdown
    conn = connect_to_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users")
        users = cursor.fetchall()
        cursor.close()
        conn.close()
    else:
        users = []

    return render_template('entries.html', users=users)


@app.route('/entriestable')
@role_required(['admin'])
def entriestable():
    # Connect to the database
    conn = connect_to_db()
    cursor = conn.cursor()

    # Fetch all audio entries from the database
    cursor.execute("SELECT * FROM audio_files")
    audio_entries = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('entriestable.html', audio_entries=audio_entries)

@app.route('/edit_entry/<int:entry_id>', methods=['POST'])
def edit_entry(entry_id):
    comment = request.form.get('comments')
    
    if comment:
        # Connect to database and update the comment field for the selected entry
        conn = connect_to_db()
        if conn:
            try:
                cursor = conn.cursor()
                update_query = """
                    UPDATE audio_files
                    SET comments = %s
                    WHERE id = %s
                """
                cursor.execute(update_query, (comment, entry_id))
                conn.commit()
                flash("Entry updated successfully!", "success")
            except Exception as e:
                flash(f"Error updating entry: {e}", "danger")
            finally:
                cursor.close()
                conn.close()
    
    return redirect(url_for('entriestable'))

@app.route('/delete_entry/<int:entry_id>', methods=['GET'])
def delete_entry(entry_id):
    # Connect to the database
    conn = connect_to_db()
    cursor = conn.cursor()

    # Delete the entry from the database
    cursor.execute("DELETE FROM audio_files WHERE id = %s", (entry_id,))
    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('entriestable'))  # Redirect to the entries table page


@app.route('/qaentries')
@role_required(['qa'])
def qaentries():
    """
    Display entries with status 'QA' for QA members.
    """
    conn = connect_to_db()
    if conn:
        cursor = conn.cursor()
        query = "SELECT * FROM audio_files WHERE status = %s"
        cursor.execute(query, ('QA',))
        qa_entries = cursor.fetchall()
        cursor.close()
        conn.close()
    else:
        qa_entries = []

    return render_template('qaentries.html', qa_entries=qa_entries)


@app.route('/userentries')
@role_required(['user'])
def userentries():
    """
    Display entries assigned to the currently logged-in user.
    """
    user_id = session.get('user_id')  # Assuming the user_id is stored in the session after login

    # Connect to the database
    conn = connect_to_db()
    if conn:
        cursor = conn.cursor()
        query = "SELECT * FROM audio_files WHERE user_id = %s"
        cursor.execute(query, (user_id,))
        user_entries = cursor.fetchall()
        cursor.close()
        conn.close()
    else:
        user_entries = []

    return render_template('userentries.html', user_entries=user_entries)

@app.route('/send_to_qa/<int:entry_id>', methods=['POST'])
@role_required(['user'])
def send_to_qa(entry_id):
    """
    Update the status of an entry to 'QA' and make it available to QA members.
    """
    conn = connect_to_db()
    if conn:
        try:
            cursor = conn.cursor()
            update_query = "UPDATE audio_files SET status = %s WHERE id = %s"
            cursor.execute(update_query, ('QA', entry_id))
            conn.commit()
            flash("Entry sent to QA successfully!", "success")
        except Exception as e:
            flash(f"Error sending entry to QA: {e}", "danger")
        finally:
            cursor.close()
            conn.close()
    return redirect(url_for('userentries'))


if __name__ == "__main__":
    app.run(debug=True)
