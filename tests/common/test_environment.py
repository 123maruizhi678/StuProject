"""本机 .env 提供配置，同名系统环境变量优先。"""
import pytest
from app.config import BASE_DIR, Settings, StudentLeaveDifySettings


def test_runtime_sources_use_local_env():
    for config_type in (Settings, StudentLeaveDifySettings):
        assert config_type.model_config['env_file'] == str(BASE_DIR / '.env')


@pytest.mark.parametrize('config_type,key_name', [
    (Settings, 'STUDENT_DIFY_KEY'),
    (StudentLeaveDifySettings, 'STUDENT_DIFY_LEAVE_KEY'),
])
def test_environment_overrides_local_file(tmp_path, monkeypatch, config_type, key_name):
    local = tmp_path / '.env'
    local.write_text(f'{key_name}=local-key\n', encoding='utf-8')
    monkeypatch.delenv(key_name, raising=False)
    config = config_type(_env_file=local)
    assert getattr(config, key_name).get_secret_value() == 'local-key'
    monkeypatch.setenv(key_name, 'environment-key')
    config = config_type(_env_file=local)
    assert getattr(config, key_name).get_secret_value() == 'environment-key'


def test_environment_overrides_credentials(tmp_path, monkeypatch):
    local = tmp_path / '.env'
    local.write_text('DB_PASSWORD=\nAUTH_SECRET_KEY=\nSTUDENT_DIFY_KEY=\n', encoding='utf-8')
    monkeypatch.setenv('DB_PASSWORD', 'test-only-injected-password')
    monkeypatch.setenv('AUTH_SECRET_KEY', 'test-only-injected-auth-secret')
    monkeypatch.setenv('STUDENT_DIFY_KEY', 'test-only-injected-workflow-key')
    config = Settings(_env_file=local)
    assert config.DB_PASSWORD == 'test-only-injected-password'
    assert config.AUTH_SECRET_KEY == 'test-only-injected-auth-secret'
    assert config.STUDENT_DIFY_KEY.get_secret_value() == 'test-only-injected-workflow-key'
