from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, User, Course, Card


app = Flask(__name__)
engine = create_engine('sqlite:///flashcard.db')

Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


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
        if name and description:
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


@app.route('/courses/<int:course_id>/edit>', methods=['GET', 'POST'])
def edit_course():
    if request.method == 'POST':
        c = session.query(Course).filter_by(id=course_id).one()
        name = request.form['name']
        description = request.form['description']
        if name and description:
            c.name = name
            c.description = description
            flash("The Course is edited")
            



    return render_template('editCourse.html')


if __name__ == '__main__':
  app.secret_key = 'super_secret_key'
  app.debug = True
  app.run(host='0.0.0.0', port=8000)