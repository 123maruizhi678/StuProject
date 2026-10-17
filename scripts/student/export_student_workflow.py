"""重建唯一Workflow中的提示词；不选择真实模型或发布应用。"""
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2]
def export():
    path=ROOT/'dify/student/student_assistant.yml'
    data=yaml.safe_load(path.read_text(encoding='utf-8'))
    nodes={n['data']['type']:n for n in data['workflow']['graph']['nodes']}
    nodes['llm']['data']['prompt_template'][0]['text']=(ROOT/'dify/student/assistant_prompt.md').read_text(encoding='utf-8')
    path.write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False),encoding='utf-8')
if __name__=='__main__':export()
