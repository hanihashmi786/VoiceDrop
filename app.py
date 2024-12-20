from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg2

app = Flask(__name__, static_folder='assets')
app.secret_key = "your_secret_key"

# Database configuration
DB_NAME = "VoiceDrop"
DB_USER = "admin"
DB_PASSWORD = "12345"
DB_HOST = "localhost"
DB_PORT = "5432"

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
        return False

    try:
        cursor = conn.cursor()
        insert_query = """
        INSERT INTO users (username, password, select_team, select_user)
        VALUES (%s, %s, %s, %s);
        """
        cursor.execute(insert_query, (username, password, select_team, select_user))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error inserting user: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


#Route for login page
@app.route('/login')
def login():
    return render_template('login.html')

# Route for dashboard page
@app.route('/dashboard')
def dashboard():
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


@app.route('/users', methods=['GET', 'POST'])
def users():
    # Fetch all teams for the dropdown
    conn = connect_to_db()
    teams = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT team_name FROM teams;")
            teams = cursor.fetchall()  # This will return a list of tuples (team_name,)
            cursor.close()
        except Exception as e:
            print(f"Error fetching teams: {e}")
        finally:
            conn.close()

    # Handle the POST request for adding a user or filtering users by team
    if request.method == 'POST':
        if 'add_user' in request.form:  # Handle Add User Form
            username = request.form.get('username')
            password = request.form.get('password')
            select_team = request.form.get('select_team')
            select_user = request.form.get('select_user')

            if username and password and select_team and select_user:
                success = insert_user(username, password, select_team, select_user)
                if success:
                    flash("User added successfully!", "success")
                else:
                    flash("Error adding user. Please try again.", "danger")
            else:
                flash("All fields are required!", "warning")
        elif 'filter_team' in request.form:  # Handle Team Filtering
            team_filter = request.form.get('team_filter')
            users_data = fetch_users(team_filter)
            return render_template('users.html', current_page='users', users=users_data, teams=teams)

    # Fetch all users if no filter is applied
    users_data = fetch_users()
    return render_template('users.html', current_page='users', users=users_data, teams=teams)

# Route for teams page
@app.route('/teams', methods=['GET', 'POST'])
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

# Route for entries page
@app.route('/entries')
def entries():
    return render_template('entries.html', current_page='entries')

# Route for entry table page
@app.route('/entriestable')
def entriestable():
    return render_template('entriestable.html', current_page='entriestable')

if __name__ == "__main__":
    app.run(debug=True)
