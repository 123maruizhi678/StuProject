"""受控职位映射；employee中的admin为企业配置角色，不等于平台admin身份。"""
from functools import lru_cache
import yaml
from app.config import BASE_DIR
from app.core.response import BusinessException

@lru_cache(maxsize=1)
def position_catalog():
    data=yaml.safe_load((BASE_DIR/'app/position_roles.yaml').read_text(encoding='utf-8'))
    allowed={'employee','consultant','manager','teacher','academic','admin'}
    if not isinstance(data,dict) or any(not isinstance(k,str) or not isinstance(v,list) or not v or any(r not in allowed for r in v) or 'employee' not in v for k,v in data.items()):
        raise RuntimeError('职位映射配置无效')
    return data

def roles_for_position(title):
    if not isinstance(title,str) or title.strip() not in position_catalog():
        raise BusinessException('职位为空或未配置，请由管理员补齐受控职位',400)
    return list(position_catalog()[title.strip()])
