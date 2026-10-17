"""只允许对服务端授权关系执行有界SELECT，模型仅引用后端参数。"""
import re
import sqlglot
from sqlglot import exp
from app.core.enterprise.enterprise_authorization import error

BANNED={'insert','update','delete','create','drop','alter','command','into','lock','with','union','intersect','except','window','offset','parameter','sessionparameter','transaction','grant','revoke'}
FUNCTIONS={'COUNT','SUM','AVG','MIN','MAX','ROUND','COALESCE','DATE','CAST','LOWER','UPPER','LENGTH','YEAR','MONTH','DAY'}
def validate_query(template,params,bound_filters,relations):
    if not isinstance(template,str) or len(template)>12000:error(400,'SQL候选无效')
    try:statements=sqlglot.parse(template,read='mysql',error_level='RAISE')
    except Exception:error(400,'SQL无法解析')
    if len(statements)!=1 or not isinstance(statements[0],exp.Select):error(400,'仅允许单个SELECT')
    tree=statements[0]
    if len(list(tree.walk()))>250 or len(list(tree.find_all(exp.Join)))>4:error(400,'查询过于复杂')
    aliases={}
    for node in tree.walk():
        if isinstance(node,(exp.Subquery,exp.Lateral,exp.TableSample)):error(400,'仅允许直接查询授权关系，不接受子查询或侧向查询')
        if node.key in BANNED:error(400,'SQL包含禁止语法')
        if isinstance(node,exp.Table):
            if node.db or node.catalog or node.name not in relations:error(403,'只能引用本次授权逻辑关系')
            aliases[node.alias_or_name]=node.name
        if isinstance(node,exp.Func):
            name=node.name.upper() if isinstance(node,exp.Anonymous) else node.sql_name().upper()
            if name not in FUNCTIONS:error(400,'SQL函数不在白名单中')
        if isinstance(node,exp.Star) and not isinstance(node.parent,exp.Count):error(400,'禁止SELECT星号或通配字段')
        if isinstance(node,exp.Literal) and node.is_string:error(400,'文本条件必须引用后端绑定参数')
        if isinstance(node,exp.Literal) and not node.is_string:
            if not isinstance(node.parent,(exp.Limit,exp.Round)):error(400,'模型不能自造数值筛选条件')
    if not aliases:error(400,'查询必须使用授权关系')
    for column in tree.find_all(exp.Column):
        if isinstance(column.this,exp.Star):continue
        if column.table:
            source=aliases.get(column.table)
            if not source or column.name not in relations[source]:error(403,'字段不在授权白名单')
        elif not any(column.name in relations[source] for source in aliases.values()):
            selected_aliases={n.alias for n in tree.expressions if n.alias}
            if column.name not in selected_aliases:error(403,'未知字段或不受控列')
    # 每个JOIN均要求显式关联字段，拒绝笛卡尔积及恒真条件。
    for join in tree.find_all(exp.Join):
        on=join.args.get('on')
        if on is None or join.args.get('kind')=='CROSS':error(400,'JOIN须声明受控主外键关系')
        pairs=[]
        if any(not isinstance(n,(exp.EQ,exp.And,exp.Column,exp.Identifier)) for n in on.walk()):error(400,'JOIN仅允许受控字段等值条件')
        for eq in on.find_all(exp.EQ):
            if isinstance(eq.left,exp.Column) and isinstance(eq.right,exp.Column):
                relation_pair=frozenset([aliases.get(eq.left.table),aliases.get(eq.right.table)])
                allowed_key={frozenset(['customers','followups']):'customer_id',frozenset(['scores','tickets']):'student_id'}.get(relation_pair)
                pairs.append(bool(allowed_key) and eq.left.name==eq.right.name==allowed_key and eq.left.table!=eq.right.table)
        if not pairs or not all(pairs):error(400,'JOIN关系不在白名单')
    used={node.name for node in tree.find_all(exp.Placeholder)}
    if not isinstance(params,dict) or set(params)!=used:error(400,'参数引用须与占位符一一对应')
    values={}
    for name,reference in params.items():
        if not re.fullmatch(r'[a-z][a-z0-9_]*',name) or reference not in bound_filters:error(400,'参数只能引用已校验筛选值')
        values[name]=bound_filters[reference]
    limit=tree.args.get('limit')
    if limit:
        item=limit.expression
        if not isinstance(item,exp.Literal) or not item.is_int or not 1<=int(item.this)<=100:error(400,'查询行数须在1至100之间')
    else:tree=tree.limit(100)
    # sqlglot MySQL的命名占位符输出为:name，交由SQLAlchemy绑定，不拼接值。
    return tree.sql(dialect='mysql'),values
