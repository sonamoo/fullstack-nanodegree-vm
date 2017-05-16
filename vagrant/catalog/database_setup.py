from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func, Boolean
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
    cards = relationship("Card")

    @property
    def serialize(self):
        """Return object data in easily serializable format"""
        card_data = [card.serialize for card in self.cards]
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'cards': card_data
        }


class Card(Base):
    __tablename__ = 'card'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    description = Column(String, nullable=False)
    memorized = Column(Integer)
    memorized_bool = Column(Boolean)
    created_on = Column(DateTime, default=func.now())
    course_id = Column(Integer, ForeignKey('course.id'))
    course = relationship(Course)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        """Return object data in easily serializable format"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }


engine = create_engine('sqlite:///flashcard.db')
Base.metadata.create_all(engine)



