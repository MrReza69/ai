from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ایجاد دیتابیس SQLite
DATABASE = 'daily_tasks.db'

def init_db():
    if not os.path.exists(DATABASE):
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''CREATE TABLE users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      username TEXT UNIQUE NOT NULL,
                      password TEXT NOT NULL,
                      name TEXT NOT NULL,
                      is_admin BOOLEAN DEFAULT FALSE,
                      last_checked DATETIME)''')
        c.execute('''CREATE TABLE groups
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT UNIQUE NOT NULL,
                      group_leader INTEGER,
                      FOREIGN KEY(group_leader) REFERENCES users(id))''')
        c.execute('''CREATE TABLE user_groups
                     (user_id INTEGER,
                      group_id INTEGER,
                      FOREIGN KEY(user_id) REFERENCES users(id),
                      FOREIGN KEY(group_id) REFERENCES groups(id))''')
        conn.commit()
        conn.close()

init_db()

class User(UserMixin):
    def __init__(self, id, username, name, is_admin=False):
        self.id = id
        self.username = username
        self.name = name
        self.is_admin = is_admin

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT id, username, name, is_admin FROM users WHERE id = ?', (user_id,))
    user_data = c.fetchone()
    conn.close()
    if user_data:
        return User(id=user_data[0], username=user_data[1], name=user_data[2], is_admin=user_data[3])
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        name = request.form.get('name')
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        try:
            c.execute('INSERT INTO users (username, password, name) VALUES (?, ?, ?)', (username, password, name))
            conn.commit()
            flash('ثبت‌نام موفقیت‌آمیز بود! لطفا وارد شوید.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('نام کاربری قبلا استفاده شده است.')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT id, username, name, is_admin FROM users WHERE username = ? AND password = ?', (username, password))
        user_data = c.fetchone()
        conn.close()
        if user_data:
            user = User(id=user_data[0], username=user_data[1], name=user_data[2], is_admin=user_data[3])
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('نام کاربری یا کلمه عبور اشتباه است.')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT last_checked FROM users WHERE id = ?', (current_user.id,))
    last_checked = c.fetchone()[0]
    c.execute('SELECT id, name, group_leader FROM groups')
    groups = c.fetchall()
    conn.close()
    return render_template('dashboard.html', last_checked=last_checked, current_user=current_user, groups=groups)

@app.route('/check', methods=['POST'])
@login_required
def check():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('UPDATE users SET last_checked = ? WHERE id = ?', (datetime.now(), current_user.id))
    conn.commit()
    conn.close()
    flash('تیک امروز شما ثبت شد!')
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/unchecked_users/<int:group_id>')
@login_required
def unchecked_users(group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # بررسی آیا کاربر مدیر یا سرپرست گروه است
    c.execute('SELECT group_leader FROM groups WHERE id = ?', (group_id,))
    group_leader = c.fetchone()[0]
    
    if not current_user.is_admin and current_user.id != group_leader:
        flash('شما دسترسی لازم برای مشاهده این لیست را ندارید.')
        return redirect(url_for('dashboard'))
    
    c.execute('''SELECT u.name FROM users u
                 JOIN user_groups ug ON u.id = ug.user_id
                 WHERE ug.group_id = ? AND (u.last_checked IS NULL OR DATE(u.last_checked) < DATE("now"))''', (group_id,))
    unchecked = [row[0] for row in c.fetchall()]
    conn.close()
    return render_template('unchecked_users.html', unchecked=unchecked)

@app.route('/join_group', methods=['POST'])
@login_required
def join_group():
    group_id = request.form.get('group_id')
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)', (current_user.id, group_id))
    conn.commit()
    conn.close()
    flash('شما به گروه اضافه شدید!')
    return redirect(url_for('dashboard'))

@app.route('/create_group', methods=['GET', 'POST'])
@login_required
def create_group():
    if not current_user.is_admin:
        flash('شما دسترسی لازم برای ایجاد گروه را ندارید.')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        group_name = request.form.get('group_name')
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        try:
            c.execute('INSERT INTO groups (name) VALUES (?)', (group_name,))
            conn.commit()
            flash('گروه با موفقیت ایجاد شد!')
        except sqlite3.IntegrityError:
            flash('نام گروه قبلا استفاده شده است.')
        finally:
            conn.close()
        return redirect(url_for('dashboard'))
    return render_template('create_group.html')

@app.route('/set_group_leader/<int:group_id>', methods=['GET', 'POST'])
@login_required
def set_group_leader(group_id):
    if not current_user.is_admin:
        flash('شما دسترسی لازم برای تنظیم سرپرست گروه را ندارید.')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        leader_id = request.form.get('leader_id')
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('UPDATE groups SET group_leader = ? WHERE id = ?', (leader_id, group_id))
        conn.commit()
        conn.close()
        flash('سرپرست گروه با موفقیت تنظیم شد!')
        return redirect(url_for('dashboard'))
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT id, name FROM users')
    users = c.fetchall()
    conn.close()
    return render_template('set_group_leader.html', group_id=group_id, users=users)

if __name__ == '__main__':
    # ایجاد یک کاربر مدیر به صورت دستی
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT id FROM users WHERE username = "admin"')
    admin_user = c.fetchone()
    if not admin_user:
        c.execute("INSERT INTO users (username, password, name, is_admin) VALUES ('admin', 'admin123', 'مدیر', True)")
        conn.commit()
    conn.close()
    app.run(debug=True)