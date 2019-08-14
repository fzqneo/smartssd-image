from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from s3dexp import config

engine = None
meta = MetaData()
Base = declarative_base(metadata=meta)

if config.DB_URI is not None:
    engine = create_engine(config.DB_URI)
    meta = MetaData(engine)
    Base = declarative_base(metadata=meta)


