"""公共账号的历史类重导出，避免第二套账号表声明。"""
from app.models.user_account import UserAccount
__all__=['UserAccount']
