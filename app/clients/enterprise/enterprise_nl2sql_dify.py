"""企业独立SQL生成协议，不调用旧question-only客户端。"""
from .enterprise_dify import EnterpriseDifyClient
def generate(inputs,user_id,client=None):return (client or EnterpriseDifyClient()).run('query',inputs,user_id)
