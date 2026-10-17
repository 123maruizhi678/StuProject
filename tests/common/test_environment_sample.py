"""公共模板只提供默认值；真实凭据来自启动环境，不加载.env。"""
from app.config import Settings, StudentLeaveDifySettings


def test_runtime_sources_use_public_sample():
    assert Settings.model_config['env_file'].endswith('.env.sample')
    assert StudentLeaveDifySettings.model_config['env_file'].endswith('.env.sample')


def test_environment_overrides_sample(tmp_path, monkeypatch):
    sample=tmp_path/'.env.sample'
    sample.write_text('DB_HOST=127.0.0.1\nDB_PASSWORD=\nAUTH_SECRET_KEY=\nSTUDENT_DIFY_KEY=\n',encoding='utf-8')
    monkeypatch.setenv('DB_PASSWORD','test-only-injected-password')
    monkeypatch.setenv('AUTH_SECRET_KEY','test-only-injected-auth-secret')
    monkeypatch.setenv('STUDENT_DIFY_KEY','test-only-injected-workflow-key')
    config=Settings(_env_file=sample)
    assert config.DB_PASSWORD=='test-only-injected-password'
    assert config.AUTH_SECRET_KEY=='test-only-injected-auth-secret'
    assert config.STUDENT_DIFY_KEY.get_secret_value()=='test-only-injected-workflow-key'
