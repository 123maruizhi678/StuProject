"""使用公共.env.sample和环境变量，通过统一应用入口启动。"""
from pathlib import Path
import argparse,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8010)
    args=parser.parse_args()
    import uvicorn
    uvicorn.run('app.main:app',host='127.0.0.1',port=args.port)
