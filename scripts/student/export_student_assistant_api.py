"""导出当前实际注册学生/协作接口，不把规划项计为已挂载。"""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.main import app
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    schema=app.openapi()
    schema['paths']={p:v for p,v in schema['paths'].items() if p.startswith(('/api/v1/student/','/api/v1/internal/student/'))}
    result=json.dumps(schema,ensure_ascii=False,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(result,encoding='utf-8')
    else:
        print(result)
