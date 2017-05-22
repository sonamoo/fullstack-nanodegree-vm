from flask import Flask, render_template, request, redirect, jsonify, url_for, flash, make_response, g
from flask import session as login_session
from sqlalchemy import create_engine, asc, desc, and_
from sqlalchemy.orm import sessionmaker
from database_setup import Base, User, Course, Card, MemorizedCard

from oauth2client import client, crypt

import hashlib
import httplib2
import os
import json

app = Flask(__name__)
engine = create_engine('sqlite:///flashcard.db')

Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

session = DBSession()
CLIENT_ID = json.loads(open('client_secret.json', 'r').read())['web']['client_id']
APPLICATION_NAME = 'flashcardapp'


@app.route('/courses/<int:course_id>/<int:card_id>/memorized')
def memorized_card(course_id, card_id):
    course = session.query(Course).filter_by(id=course_id).one()
    card = session.query(Card).filter_by(id=card_id).one()
    if is_user_logged_in(login_session):
        user_id = get_user_id(login_session)
        if user_id == card.user_id:
            learned_card = MemorizedCard(name=card.name, description=card.description, user_id=user_id, course_id=course_id, card_id=card_id)
            session.add(learned_card)
            session.commit()
            flash("Memorized %s!" % card.name)
            return redirect(url_for('card_detail', course_id=course.id, card_id=card.id))
        else:
            return "You are not authorized to do this task."
    else:
        flash("You need to login")
        return redirect(url_for('login'))


@app.route('/courses/<int:course_id>/<int:card_id>/cancelMemorized')
def cancel_memorized_card(course_id, card_id):
    card = session.query(Card).filter_by(id=card_id).one()
    if is_user_logged_in(login_session):
        user_id = get_user_id(login_session)

        card_to_delete = session.query(MemorizedCard).filter(and_(MemorizedCard.card_id == card.id, MemorizedCard.user_id == user_id, MemorizedCard.course_id == course_id)).one()
        flash("successfully un memorized!? %s" % card_to_delete.name)
        session.delete(card_to_delete)
        session.commit()
        return redirect(url_for('card_detail', course_id=course_id, card_id=card_id))

    else:
        flash("You are not logged in")
        return redirect(url_for('login'))


@app.route('/users/<int:user_id>/memorized')
def show_memorized_cards(user_id):
    if is_user_logged_in(login_session):
        if get_user_id(login_session) == user_id:
            courses = session.query(Course).all()
            user = get_user_info(login_session)

            all_cards_list = []
            for course in courses:
                card_dict = {}
                card_dict['course'] = course
                cards_of_course_list = []
                memorized_cards = session.query(MemorizedCard).filter(and_(MemorizedCard.user_id == user.id, MemorizedCard.course_id == course.id )).all()
                for card in memorized_cards:
                    cards_of_course_list.append(card)
                card_dict['cards'] = cards_of_course_list
                all_cards_list.append(dict(card_dict))
            return render_template('showMemorizedCards.html', all_cards_list=all_cards_list)
        else:
            return "you are not authorized to see this page"
    else:
        flash("You need to login")
        return redirect(url_for('login'))



@app.route('/users')
def get_users():
    users = session.query(User).all()
    return render_template('users.html', users=users)


@app.route('/login')
def login():
    state = hashlib.sha256(os.urandom(1024)).hexdigest()
    print "state: " + state
    login_session['state'] = state
    return render_template('login.html',
                           STATE=state,
                           CLIENT_ID=CLIENT_ID)


@app.route('/logout')
def logout():
    return render_template('logout.html',
                           CLIENT_ID=CLIENT_ID)


@app.route('/oauth2callback', methods=['POST'])
def oauth2callback():
    # receive the state from the client and compare the state created from the server
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # get the id_token from the client
    id_token = request.data

    # check issuer if the id token issued by google
    try:
        idinfo = client.verify_id_token(id_token, CLIENT_ID)
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise crypt.AppIdentityError("Wrong issuer.")
    except crypt.AppIdentityError:
        response = make_response(json.dumps('Invalid token.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    gplus_id = idinfo['sub']
    url = 'https://www.googleapis.com/oauth2/v3/tokeninfo?id_token=%s' % id_token
    h = httplib2.Http()
    data = json.loads(h.request(url, 'GET')[1])

    # Verify that the id token is used for the intended user.
    if data['sub'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the id token is for this app
    if data['aud'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check if the user is already logged in.
    stored_id_token = login_session.get('id_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_id_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Save user information to the login session.
    login_session['id_token'] = id_token
    login_session['gplus_id'] = gplus_id
    login_session['provider'] = 'google'
    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    print "Now wa re doing that is problematic"
    user_id = get_user_id(login_session)
    # if this user does not existed in the database
    print " I don't understand why user_id is None"
    print user_id

    if not user_id:
        user_id = create_user(login_session) # create a user in the database
    login_session['user_id'] = user_id

    result = "Successfully logged in!!!!"
    return result


@app.context_processor
def inject_user():

    if is_user_logged_in(login_session):
        print "user is logged in."
        email = login_session['email']
        username = login_session['username']
        id = get_user_id(login_session)
        user = {'username': username, 'email': email, 'id': id}
        g.user = user
        return dict(user=g.user)
    else:
        return dict(user=None)


@app.route('/courses/JSON')
def all_courses_json():
    courses = session.query(Course).all()
    courses_list = [course.serialize for course in courses]
    return jsonify(Category=courses_list)


@app.route('/courses/<course_id>/cards/JSON')
def course_cards_json(course_id):
    cards = session.query(Card).filter_by(course_id=course_id).all()
    cards_list = [c.serialize for c in cards]
    return jsonify(cards=cards_list)


@app.route('/courses/cards/JSON')
def all_cards():
    cards = session.query(Card).all()
    cards_list = [c.serialize for c in cards]
    return jsonify(cards=cards_list)


@app.route('/')
@app.route('/courses/')
def show_courses():
    courses = session.query(Course).order_by(asc(Course.name))
    return render_template('courses.html', courses=courses)

@app.route('/cards')
def show_all_cards():

    courses = session.query(Course).order_by(asc(Course.name))
    all_cards_list = []
    cards_dict = {}

    for course in courses:
        cards_of_course = []
        cards_dict['course'] = course

        cards = session.query(Card).filter_by(course_id=course.id).all()


        for card in cards:
            cards_of_course.append(card)

        cards_dict['cards'] = cards_of_course
        all_cards_list.append(dict(cards_dict))

    return render_template('cards.html', courses_list=all_cards_list)


@app.route('/courses/new', methods=['GET', 'POST'])
def new_course():
    if is_user_logged_in(login_session) is False:
        flash("You need to login to add more courses!")
        return redirect(url_for('login'))

    user = session.query(User).filter_by(id=get_user_id(login_session)).one()
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        course_name_list = []
        if name and description:
            courses = session.query(Course).order_by(asc(Course.name))
            for c in courses:
                lowcase_name = c.name.lower()
                course_name_list.append(lowcase_name)
            if name.lower() in course_name_list:
                flash("The %s course is already exists" % name)
                return render_template('newCourse.html', description=description, name=name)
            else:
                created_course = Course(name=name, description=description, user_id=user.id, created_by=user.name)
                session.add(created_course)
                session.commit()
                flash('New Course %s Successfully Created' % created_course.name)
                return redirect(url_for('show_courses'))
        else:
            flash("We need both name and description")
            return render_template('newCourse.html')
    else:
        return render_template('newCourse.html')


@app.route('/courses/<int:course_id>/edit', methods=['GET', 'POST'])
def edit_course(course_id):

    c = session.query(Course).filter_by(id=course_id).one()
    if get_user_id(login_session) != c.user_id:
        return "You don't own this course"

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        if name and description:
            c.name = name
            c.description = description
            session.add(c)
            session.commit()
            flash("The Course is edited")
            return redirect(url_for('show_courses'))
    else:
        return render_template('editCourse.html', course=c)


@app.route('/courses/<int:course_id>/delete', methods=['GET', 'POST'])
def delete_course(course_id):
    c = session.query(Course).filter_by(id=course_id).one()
    if is_user_logged_in(login_session) is False:
        flash("You need to login to delete a card!")
        return redirect(url_for('login'))
    if get_user_id(login_session) != c.user_id:
        return "This course is not created by you."
    if request.method == 'POST':
        session.delete(c)
        flash("Succesfully deleted %s" % c.name)
        session.commit()
        return redirect(url_for('show_courses'))
    else:
        return render_template('deleteCourse.html', course=c)


@app.route('/courses/<int:course_id>/cards', methods=['GET'])
def show_cards(course_id):
    cards = session.query(Card).filter_by(course_id=course_id)
    course = session.query(Course).filter_by(id=course_id).one()
    courses = session.query(Course).order_by(asc(Course.name))
    number_of_cards = session.query(Card).filter_by(course_id=course_id).count()
    return render_template('showCards.html', cards=cards, course=course,
                           courses=courses, number_of_cards=number_of_cards)


@app.route('/courses/<int:course_id>/cards/new', methods=['GET', 'POST'])
def new_card(course_id):
    if is_user_logged_in(login_session) is False:
        flash("You need to login to add more cards!")
        return redirect(url_for('login'))
    course = session.query(Course).filter_by(id=course_id).one()
    user = session.query(User).filter_by(id=get_user_id(login_session)).one()
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        if name and description:
            cards = session.query(Card).filter_by(course_id=course.id)
            cards_name_list = []
            for c in cards:
                lowercase_name = c.name.lower()
                cards_name_list.append(lowercase_name)
            if name.lower() in cards_name_list:
                flash("The %s card is already exists" % name)
                return render_template('newCard.html', course=course, description=description, name=name)
            else:
                created_card = Card(name=name, description=description, course_id=course_id, created_by=user.name, user_id=user.id)
                session.add(created_card)
                session.commit()
                flash("Successfully created %s" % created_card.name)
                return redirect(url_for('show_cards', course_id=course.id))
        else:
            flash("We need both name and description")
            return render_template('newCard.html', course=course, description=description, name=name)
    else:
        return render_template('newCard.html', course=course)


@app.route('/courses/<int:course_id>/<int:card_id>')
def card_detail(course_id, card_id):
    course = session.query(Course).filter_by(id=course_id).one()
    card = session.query(Card).filter_by(id=card_id).one()
    cards = session.query(Card).filter_by(course_id=course_id).order_by(asc(Card.name))
    courses = session.query(Course).order_by(asc(Course.name))
    cards_id_list = []
    # If user is logged in.
    if is_user_logged_in(login_session):
        user_id = get_user_id(login_session)
        memorized_cards = get_user_memorized_cards(user_id)
        memorized_cards_id_list = []
        # Create list that contains original id of the card.
        for c in memorized_cards:
            # Verify if user owns the memorized card.
            memorized_cards_id_list.append(c.card_id)
        for c in cards:
            cards_id_list.append(c.id)
        len_of_cards = len(cards_id_list)
        card_index = cards_id_list.index(card.id)
        if card.course_id != course.id:
            flash("There is no %s card in the %s " % (card.name, course.name))
            return redirect(url_for('show_cards', course_id=course.id))
        else:
            return render_template('card_detail.html',
                                   course=course,
                                   courses=courses,
                                   card=card,
                                   cards=cards,
                                   card_index=card_index,
                                   cards_id_list=cards_id_list,
                                   len_of_cards=len_of_cards,
                                   memorized_cards_id_list=memorized_cards_id_list)
    # If user is not logged in.
    else:
        for c in cards:
            cards_id_list.append(c.id)
        len_of_cards = len(cards_id_list)
        card_index = cards_id_list.index(card.id)
        if card.course_id != course.id:
            flash("There is no %s card in the %s " % (card.name, course.name))
            return redirect(url_for('show_cards', course_id=course.id))
        else:
            return render_template('card_detail.html',
                                   course=course,
                                   courses=courses,
                                   card=card,
                                   cards=cards,
                                   card_index=card_index,
                                   cards_id_list=cards_id_list,
                                   len_of_cards=len_of_cards)


@app.route('/courses/<int:course_id>/<int:card_id>/edit', methods=['GET', 'POST'])
def edit_card(course_id, card_id):
    card = session.query(Card).filter_by(id=card_id).one()
    course = session.query(Course).filter_by(id=course_id).one()
    if is_user_logged_in(login_session) is False:
        flash("You need to login to delete a card!")
        return redirect(url_for('login'))
    if get_user_id(login_session) != card.user_id:
        return "You don't own this card"
    if card.course_id != course.id:
        flash("There is no %s card in the %s " % (card.name, course.name))
        return redirect(url_for('show_cards', course_id=course.id))
    else:
        if request.method == 'POST':
            name = request.form['name']
            description = request.form['description']
            if name and description:
                card.name = name
                card.description = description
                session.add(card)
                session.commit
                flash('The card is edited')
                return redirect(url_for('card_detail', course_id=course.id, card_id=card.id))
            else:
                flash('Both card name and description are needed.')
                return render_template('editCard.html', card=card, course=course)
        else:
            return render_template('editCard.html', card=card, course=course)


@app.route('/courses/<int:course_id>/<int:card_id>/delete', methods=['GET', 'POST'])
def delete_card(course_id, card_id):
    card = session.query(Card).filter_by(id=card_id).one()
    course = session.query(Course).filter_by(id=course_id).one()
    if is_user_logged_in(login_session) is False or get_user_id(login_session) != card.user_id:
        flash("You are not authorized to delete this card!")
        return redirect(url_for('login'))

    if card.course_id != course.id:
        flash("There is no %s card in the %s " % (card.name, course.name))
        return redirect(url_for('show_cards', course_id=course.id))
    else:
        if request.method == 'POST':
            previous_card = session.query(Card).order_by(desc(Card.id)).filter(and_(Card.id < card.id, Card.course_id == course.id)).first()
            if previous_card == None:
                next_card = session.query(Card).order_by(asc(Card.id)).filter(and_(Card.id > card.id, Card.course_id == course.id)).first()
                if next_card == None:
                    session.delete(card)
                    session.commit()
                    flash("You deleted all the cards from %s. Create cards and start learning again!" % course.name)
                    return redirect(url_for('show_cards', course_id=course.id))
                else:
                    session.delete(card)
                    flash("Succesfully deleted %s from %s " % (card.name, course.name))
                    session.commit()
                    return redirect(url_for('card_detail', course_id=course.id, card_id=next_card.id))
            else:
                session.delete(card)
                flash("Succesfully deleted %s from %s " % (card.name, course.name ))
                session.commit()
                return redirect(url_for('card_detail', course_id=course.id, card_id=previous_card.id), )
        else:
            return render_template('deleteCard.html', card=card, course=course)


@app.route('/clearSession')
def clearSession():
    login_session.clear()
    flash("Successfully logged out")
    return redirect(url_for('show_courses'))


def create_user(login_session):
    new_user = User(name=login_session['username'],
                    email=login_session['email'],
                    picture=login_session['picture'])
    session.add(new_user)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def get_user_memorized_cards(user_id):
    memorized_cards = session.query(MemorizedCard).filter_by(user_id=user_id).all()
    return memorized_cards


def get_user_info(login_session):
    user_id = get_user_id(login_session)
    user = session.query(User).filter_by(id=user_id).one()
    return user


def is_user_logged_in(login_session):
    if 'username' not in login_session:
        return False
    else:
        return True


def get_user_id(login_session):
    try:
        user = session.query(User).filter_by(email=login_session['email']).one()
        return user.id
    except:
        return None



if __name__ == '__main__':
  app.secret_key = 'super_secret_key'
  app.debug = True
  app.run(host='0.0.0.0', port=8000)