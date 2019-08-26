import s3dexp.db

from sqlalchemy.orm import sessionmaker


def get_session():
    Session = sessionmaker()
    Session.configure(bind=s3dexp.db.engine)
    session = Session()
    return session


def insert_or_update_one(sess, model, keys_dict, vals_dict):
    if sess is None:
        return None
    # expect one or no row, otherwise raises error
    record = sess.query(model).filter_by(**keys_dict).one_or_none()
    if record is not None:
        sess.query(model).filter_by(**keys_dict).update(vals_dict)
    else:
        create_dict = {}
        create_dict.update(keys_dict)
        create_dict.update(vals_dict)
        record = model(**create_dict)
        sess.add(record)
    return record