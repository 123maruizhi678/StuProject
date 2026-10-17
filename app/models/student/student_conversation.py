"""学生会话及轮次占位，共用唯一元数据。"""
from sqlalchemy import Table, Column, String, Integer, DateTime, JSON, Text, ForeignKey, ForeignKeyConstraint, UniqueConstraint
from app.database import Base
from sqlalchemy import BigInteger, Integer
identifier = BigInteger().with_variant(Integer, "sqlite")
sid_type = String(64, collation='utf8mb4_bin').with_variant(String(64, collation='BINARY'), 'sqlite')
sessions = Table('student_assistant_session', Base.metadata,
    Column('session_id',sid_type,primary_key=True),
    Column('student_id',identifier,ForeignKey('student_profile.student_id'),nullable=False),
    Column('version',Integer,nullable=False,server_default='1'), Column('created_at',DateTime,nullable=False),Column('updated_at',DateTime,nullable=False),
    UniqueConstraint('session_id','student_id',name='uq_assistant_session_owner'))
turns = Table('student_assistant_turn', Base.metadata,
    Column('id',identifier,primary_key=True,autoincrement=True),
    Column('session_id',sid_type,nullable=False),
    Column('student_id',identifier,ForeignKey('student_profile.student_id'),nullable=False),
    Column('request_key',String(128),nullable=False), Column('parameters_hash',String(64),nullable=False),
    Column('message',Text,nullable=False), Column('result',JSON(none_as_null=True),nullable=True),Column('created_at',DateTime,nullable=False),
    ForeignKeyConstraint(['session_id','student_id'],['student_assistant_session.session_id','student_assistant_session.student_id']),
    UniqueConstraint('student_id','request_key',name='uq_assistant_turn_request'))

sessions.comment="学生助手会话归属及并发版本"
for column in sessions.c:
    column.comment={"session_id":"会话编号；会话唯一标识","student_id":"所属学生编号；所属学生内部主键","version":"并发版本号；会话并发版本号","created_at":"创建时间；创建时间（UTC）","updated_at":"最近修改时间；最近更新时间（UTC）"}[column.name]

turns.comment="学生助手对话轮次、请求去重及结果回执"
for column in turns.c:
    column.comment={"id":"记录主键；对话轮次主键","session_id":"会话编号；会话唯一标识","student_id":"所属学生编号；所属学生内部主键","request_key":"请求幂等键摘要；本次请求幂等键摘要","parameters_hash":"请求参数摘要；规范化请求正文摘要","message":"学生消息正文；学生本轮消息文本","result":"本轮响应与回执；本轮响应及业务预览回执（JSON）","created_at":"创建时间；创建时间（UTC）"}[column.name]
