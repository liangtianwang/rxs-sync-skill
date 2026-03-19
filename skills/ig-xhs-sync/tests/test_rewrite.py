import pytest
from unittest.mock import MagicMock, patch


def test_rewrite_returns_string():
    """rewrite_caption returns a non-empty string."""
    from rewrite import rewrite_caption
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text="好美的一天！☀️ #旅行 #生活")
    ]
    result = rewrite_caption("Beautiful day!", mock_client)
    assert isinstance(result, str)
    assert len(result) > 0


def test_rewrite_calls_correct_model():
    """rewrite_caption uses claude-haiku-4-5-20251001."""
    from rewrite import rewrite_caption
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text="测试内容 #标签")
    ]
    rewrite_caption("test", mock_client)
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"


def test_rewrite_empty_caption_returns_fallback():
    """Empty caption produces a fallback note, not an empty string."""
    from rewrite import rewrite_caption
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text="✨ 分享生活点滴 #日常 #生活")
    ]
    result = rewrite_caption("", mock_client)
    assert len(result) > 0


def test_rewrite_api_error_raises():
    """API errors propagate so sync.py can catch and skip the post."""
    from rewrite import rewrite_caption
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("rate limit")
    with pytest.raises(Exception, match="rate limit"):
        rewrite_caption("some caption", mock_client)
