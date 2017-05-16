from flask import Flask, render_template, request, redirect, jsonify, url_for, flash, make_response
from flask import session as login_session
from sqlalchemy import create_engine, asc, desc, and_
from sqlalchemy.orm import sessionmaker
from database_setup import Base, User, Course, Card

from oauth2client.client import flow_from_clientsecrets
from apiclient import discovery
from oauth2client import client, crypt

import hashlib
import os
import json


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


@app.route('/oauth2callback', methods=['POST'])
def gconnect():
    print "Im here /oauth2callback"
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    code = request.data
    print code
    return code


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

if __name__ == '__main__':
  app.secret_key = 'super_secret_key'
  app.debug = True
  app.run(host='0.0.0.0', port=8000)