"""shared.metrics.prome.extract_usage 的 token 解析测试。"""
from shared.metrics.prome import extract_usage


class _WithUsageMetadata:
    usage_metadata = {
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "output_token_details": {"reasoning": 2},
    }
    response_metadata = None


class _WithTokenUsage:
    usage_metadata = None
    response_metadata = {"token_usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}}


class _WithUsageAlt:
    usage_metadata = None
    response_metadata = {
        "usage": {
            "input_tokens": 1,
            "output_tokens": 2,
            "total_tokens": 3,
            "completion_tokens_details": {"reasoning_tokens": 1},
        },
    }


class _Empty:
    usage_metadata = None
    response_metadata = None


def test_usage_metadata_path():
    assert extract_usage(_WithUsageMetadata()) == {
        "input": 10, "output": 5, "reasoning": 2, "total": 15,
    }


def test_response_metadata_token_usage():
    usage = extract_usage(_WithTokenUsage())
    assert usage["input"] == 7
    assert usage["output"] == 3
    assert usage["total"] == 10


def test_response_metadata_usage_alt():
    usage = extract_usage(_WithUsageAlt())
    assert usage == {"input": 1, "output": 2, "reasoning": 1, "total": 3}


def test_no_metadata_returns_zeros():
    assert extract_usage(_Empty()) == {"input": 0, "output": 0, "reasoning": 0, "total": 0}
