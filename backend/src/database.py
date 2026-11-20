import os
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker,DeclarativeBase
url=os.environ['DATABASE_URL']
if url.startswith('sqlite'):
 # 本地开发兜底：生产仍用MySQL READ COMMITTED；SQLite以BEGIN IMMEDIATE串行化写事务
 engine=create_engine(url,pool_pre_ping=True,connect_args={'timeout':30})
 @event.listens_for(engine,'begin')
 def _begin(conn):conn.exec_driver_sql('BEGIN IMMEDIATE')
else:engine=create_engine(url,pool_pre_ping=True,isolation_level='READ COMMITTED')
Session=sessionmaker(engine,expire_on_commit=False)
class Base(DeclarativeBase):pass
