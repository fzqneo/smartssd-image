from s3dexp.db import Base
import sqlalchemy as sa

class ImageMeta(Base):
    __tablename__ = 'ImageMeta'
    id = sa.Column(sa.Integer, primary_key=True)
    path = sa.Column(sa.String(1024), nullable=False)
    format = sa.Column(sa.String(20))
    size = sa.Column(sa.Integer)
    width = sa.Column(sa.Integer)
    height = sa.Column(sa.Integer)
    channel = sa.Column(sa.Integer)

    
class DiskReadProfile(Base):
    __tablename__ = 'DiskReadProfile'
    id = sa.Column(sa.Integer, primary_key=True)
    path = sa.Column(sa.String(1024), nullable=False)
    disk = sa.Column(sa.String(20))
    seq_read_ms = sa.Column(sa.Float(53))
    rand_read_ms = sa.Column(sa.Float(53))
    size = sa.Column(sa.Integer)
