from flask import Flask, render_template, request, redirect, jsonify, url_for, flash, make_response
from flask import session as login_session
from sqlalchemy import create_engine, asc, desc, and_
from sqlalchemy.orm import sessionmaker
from database_setup import Base, User, Course, Card

from oauth2client.client import flow_from_clientsecrets
from apiclient import discovery
from oauth2client import client

import hashlib
import httplib2
import os
import json
import requests

app = Flask(__name__)
engine = create_engine('sqlite:///flashcard.db')

Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

session = DBSession()
CLIENT_ID = json.loads(open('client_secret.json', 'r').read())['web']['client_id']
APPLICATION_NAME = 'flashcardapp'


@app.route('/login')
def login():
    state = hashlib.sha256(os.urandom(1024)).hexdigest()
    print "state: " + state
    login_session['state'] = state
    return render_template('login.html',
                           STATE=state,
                           CLIENT_ID=CLIENT_ID,
                           APPLICATION_NAME=APPLICATION_NAME)


@app.route('/oauth2callback', methods=['GET'])
def oauth2callback():
    # create a flow to implement OAuth process.
    flow = client.flow_from_clientsecrets(
        'client_secret.json',
        scope='openid profile email',
        redirect_uri='http://localhost:8000/oauth2callback'
    )

    if 'code' not in request.args:
        auth_uri = flow.step1_get_authorize_url()
        return redirect(auth_uri)
    else:
        auth_code = request.args.get('code')
        credentials = flow.step2_exchange(auth_code)

        if credentials.access_token_expired:
            return redirect(url_for('oauth2callback'))
        else:
            access_token = credentials.access_token
            url = ('https://www.googleapis.com/oauth2/v2/tokeninfo?access_token=%s'
                   % access_token)
            h = httplib2.Http()
            result = json.loads(h.request(url, 'GET')[1])

            # if there is an error in access token info, abort
            if result.get('error') is not None:
                response = make_response(json.dumps(result.get('error')), 500)
                response.headers['Content-Type'] = 'application/json'
                return response

            # Verify that the access token is used for the intended user.
            gplus_id = credentials.id_token['sub']
            if result['user_id'] != gplus_id:
                response = make_response(
                    json.dumps("Token's user ID doesn't match given user ID."), 401)
                response.headers['Content-Type'] = 'application/json'
                return response

            # Verify that the access token is valid for this app.
            if result['issued_to'] != CLIENT_ID:
                response = make_response(
                    json.dumps("Token's client ID does not match app's."), 401)
                print "Token's client ID does not match app's."
                response.headers['Content-Type'] = 'application/json'
                return response

            # Check if the user is already logged in.
            stored_access_token = login_session.get('access_token')
            stored_gplus_id = login_session.get('gplus_id')
            if stored_access_token is not None and gplus_id == stored_gplus_id:
                response = make_response(json.dumps('Current user is already connected.'),200)
                response.headers['Content-Type'] = 'application/json'
                return response

            login_session['access_token'] = credentials.access_token
            login_session['gplus_id'] = gplus_id

            userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            params = {'access_token': credentials.access_token, 'alt': 'json'}
            answer = requests.get(userinfo_url, params=params)
            data = answer.json()

            login_session['provider'] = 'google'
            login_session['username'] = data['name']
            login_session['picture'] = data['picture']
            login_session['email'] = data['email']

            # now validate the contents in the 'result' json object.
            user_id = get_user_id(login_session['email'])
            if not user_id:
                user_id = create_user(login_session)
            login_session['user_id'] = user_id

            return render_template('welcome.html', username=login_session['username'], email=login_session['email'] )


@app.route('/logout')
def logout():
    if 'access_token' in login_session:
        access_token = login_session['access_token']
        print 'In gdisconnect access token is %s', access_token
        print 'User name is: '
        print login_session['username']
        if access_token is None:
            print 'Access Token is None'
            response = make_response(json.dumps('Current user not connected.'), 401)
            response.headers['Content-Type'] = 'application/json'
            return response
        url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % login_session['access_token']
        h = httplib2.Http()
        result = h.request(url, 'GET')[0]
        print 'result is '
        print result
        print result.status
        print type(result.status)
        if result.status == 200:
            del login_session['access_token']
            del login_session['gplus_id']
            del login_session['username']
            del login_session['email']
            del login_session['picture']
            response = make_response(json.dumps('Successfully disconnected.'), 200)
            response.headers['Content-Type'] = 'application/json'
            return response
        else:
            response = make_response(json.dumps('Failed to revoke token for given user.', 400))
            response.headers['Content-Type'] = 'application/json'
            return response
    else:
        return "You are not logged in."



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


@app.route('/courses/new', methods=['GET', 'POST'])
def new_course():
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
                created_course = Course(name=name, description=description)
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
    if request.method == 'POST':
        session.delete(c)
        flash("Succesfully deleted %s" % c.name)
        session.commit()
        return redirect(url_for('show_courses'))
    else:
        return render_template('deleteCourse.html', course=c)


@app.route('/courses/<int:course_id>/cards')
def show_cards(course_id):
    cards = session.query(Card).filter_by(course_id=course_id)
    course = session.query(Course).filter_by(id=course_id).one()
    courses = session.query(Course).order_by(asc(Course.name))
    number_of_cards = session.query(Card).filter_by(course_id=course_id).count()
    return render_template('showCards.html', cards=cards, course=course,
                           courses=courses, number_of_cards=number_of_cards)


@app.route('/courses/<int:course_id>/cards/new', methods=['GET', 'POST'])
def new_card(course_id):
    course = session.query(Course).filter_by(id=course_id).one()
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
                created_card = Card(name=name, description=description, course_id=course_id)
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
    for c in cards:
        cards_id_list.append(c.id)
    len_of_cards = len(cards_id_list)
    card_index = cards_id_list.index(card.id)
    if card.course_id != course.id:
        flash("There is no %s card in the %s " % (card.name, course.name))
        return redirect(url_for('show_cards', course_id=course.id))
    else:
        print "card_index: "
        print card_index
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


def get_user_info(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def is_user_logged_in(login_session):
    if 'username' not in login_session:
        return redirect('/login')

def get_user_id(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


if __name__ == '__main__':
  app.secret_key = 'super_secret_key'
  app.debug = True
  app.run(host='0.0.0.0', port=8000)