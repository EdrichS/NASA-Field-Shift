from app.config import Settings


def test_blank_values_keep_defaults(tmp_path):
    env = tmp_path / ".env"
    env.write_text("XAI_BASE_URL=\nFRONTEND_ORIGINS=\nEE_PROJECT=my-project\n")
    s = Settings(_env_file=env)
    assert s.xai_base_url == "https://api.x.ai/v1"
    assert s.cors_origins == ["http://localhost:5173"]
    assert s.ee_project == "my-project"


def test_origins_split_on_commas():
    s = Settings(_env_file=None, frontend_origins="http://localhost:5173, https://x.trycloudflare.com")
    assert s.cors_origins == ["http://localhost:5173", "https://x.trycloudflare.com"]


def test_secrets_never_show_in_repr():
    s = Settings(_env_file=None, xai_api_key="xai-super-secret", database_url="postgres://u:pw@h/db")
    assert "xai-super-secret" not in repr(s)
    assert "pw@h" not in repr(s)
