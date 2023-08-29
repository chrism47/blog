import smtplib
from datetime import date
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, request, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm, ContactForm
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
# a massive pile of dependencies

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
# limiter = Limiter(get_remote_address, app=app)

ckeditor = CKEditor(app)
Bootstrap(app)
# configure BS CKE and flask, load_dotenv() for env variables


app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# connect the db with flask and sqlalch

login_manager = LoginManager(app)
# flask validation?

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    category = db.Column(db.String(80), nullable=False, server_default="default_value")

    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    comments = db.relationship('Comments', backref='blog_post', cascade='all, delete-orphan')
    #set up db relationships around posts

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    password = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), nullable=False)

    blog_posts = db.relationship('BlogPost', backref='user')
    #the structure of the user profile. It is related to posts via relational mapping

    def __init__(self, name, email, password):
        self.email = email
        self.password = password
        self.name = name

    #user info
    def get_id(self):
        return str(self.id)
    #
class Comments(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    name = db.Column(db.String, nullable=False)
    date = db.Column(db.Integer, nullable=False)
    blog_post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'), nullable=False)
    #the foreign key
db.create_all()
# this is an if-necessary piece for db building

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)
#get the user id of the current user and store it in the user_loader

def admin_only(route_function):
    @wraps(route_function)
    def check_id():
        if current_user.is_authenticated and current_user.id == 1:
            return route_function()
        else:
            abort(403)
    return check_id
#decorator for creating admin only privileges, (auth + id match)

@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    posts.reverse()
    return render_template("index.html", all_posts=posts)
#pull all posts and order by newest post on top

@app.route('/register', methods=['POST', 'GET'])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        email = form.email.data
        db_query = User.query.filter_by(email=email).first()

        if db_query is None:
            password_base = form.password.data
            password = generate_password_hash(password_base, method='pbkdf2:sha256', salt_length=8)
            new_user = User(
                name=form.name.data,
                email=email,
                password=password
            )
            db.session.add(new_user)
            db.session.commit()
            user = User.query.filter_by(email=form.email.data).first()
            login_user(user)
            posts = BlogPost.query.all()
            return render_template("index.html", all_posts=posts)
        elif db_query.email == email:
            flash("There is already an account using this email. Try logging in?")
            return redirect(url_for('login'))
    return render_template("register.html", form=form)



@app.route('/login', methods=['POST', 'GET'])
def login():
    form = LoginForm()
    if request.method == 'POST':
        email = form.email.data
        password = form.password.data
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            name = user.name
            login_user(user)
            posts = BlogPost.query.all()
            return render_template("index.html", all_posts=posts)
        elif not user:
            flash("There is no account with this email address.")
        elif not check_password_hash(user.password, password):
            flash("Incorrect password.")
    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    comment_form = CommentForm()
    comments = Comments.query.limit(20).all()
    comments.reverse()

    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("Please login, if you would like to comment.")
            return redirect(url_for('login'))
        else:
            new_comment = Comments(
                body=comment_form.body.data,
                id=current_user.id,
                name=current_user.name,
                date=date.today().strftime("%B %d, %Y"),
                blog_post_id=post_id

            )
            db.session.add(new_comment)
            db.session.commit()

            return redirect(url_for('show_post',
                                    comments=comments,
                                    post=requested_post,
                                    comment_form=comment_form,
                                    post_id=post_id))

    return render_template("post.html",
                           comments=comments,
                           post=requested_post,
                           comment_form=comment_form)


@app.route("/about")
def about():

    return render_template("about.html")


@app.route("/contact", methods=['POST', 'GET'])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        form_data = [request.form['name'],
                     request.form['email'],
                     request.form['phone'],
                     request.form['message']
                     ]
        my_email = os.getenv('MY_EMAIL')
        password = os.getenv('EMAIL_PASSWORD')

        with smtplib.SMTP('smtp.gmail.com', 587, timeout=120) as connection:
            connection.starttls()
            connection.login(user=my_email, password=password)
            connection.sendmail(from_addr=request.form['email'],
                                to_addrs=my_email,
                                msg=f"{request.form['message']} \n\n"
                                    f"Name: {request.form['name']} \n"
                                    f"Phone: {request.form['phone']}"
                                )
            print('Email successfully sent!')
        print(form_data)
        success = "Successfully sent, thank you!"
        return render_template('contact.html', form=form, message=success)
    else:
        contact_me = "Contact Me"
        return render_template('contact.html', form=form, message=contact_me)



@admin_only
@app.route("/new-post", methods=["POST", "GET"])
@login_required
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            category=form.category.data,
            img_url=form.img_url.data,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)

@admin_only
@app.route("/edit-post/<int:post_id>", methods=["POST", "GET"])
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        id=post.id,
        body=post.body,
        category=post.category
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        post.category = edit_form.category
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)

@admin_only
@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))

@admin_only
@app.route("/delete_comment/<int:post_id>")
def delete_comment(post_id):
    comment_to_delete = Comments.query.get(post_id)
    db.session.delete(comment_to_delete)
    db.session.commit()
    return redirect(url_for('show_post', post_id=post_id))



if __name__ == "__main__":

    app.run(host='0.0.0.0', port=5000)
