from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship


Base = declarative_base()


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    pw_hash = Column(String, nullable=False)
    name = Column(String(250), nullable=False)
    email = Column(String(250), nullable=False)
    picture = Column(String(250))

    def __repr__(self):
        return "<User(Name: '%s', pw: '%s')>" % (self.name, self.pw_hash)


class Course(Base):
    __tablename__ = 'course'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    description = Column(String(200))
    created_on = Column(DateTime, default=func.now())
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)


class Card(Base):
    __tablename__ = 'card'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    description = Column(String, nullable=False)
    memorized = Column(Integer)
    created_on = Column(DateTime, default=func.now())
    course_id = Column(Integer, ForeignKey('course.id'))
    course = relationship(Course)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)


engine = create_engine('sqlite:///flashcard.db')
Base.metadata.create_all(engine)



