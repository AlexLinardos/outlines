import os
import re
import warnings
from typing import AsyncGenerator, Generator

import pytest
from openai import AsyncOpenAI, OpenAI

from outlines.models.vllm import VLLM, AsyncVLLM, from_vllm
from outlines.types.dsl import CFG, Regex, JsonSchema
from tests.test_utils.mock_openai_client import MockOpenAIClient, MockAsyncOpenAIClient


YES_NO_GRAMMAR = """
?start: answer

answer: "yes" | "no"
"""


# If the VLLM_SERVER_URL environment variable is set, use the real vLLM server
# Otherwise, use the mock server
vllm_server_url = os.environ.get("VLLM_SERVER_URL")
vllm_model_name = os.environ.get(
    "VLLM_MODEL_NAME", "microsoft/Phi-3-mini-4k-instruct"
)
if vllm_server_url:
    openai_client = OpenAI(base_url=vllm_server_url)
    async_openai_client = AsyncOpenAI(base_url=vllm_server_url)
else:
    warnings.warn("No VLLM server URL provided, using mock server")
    openai_client = MockOpenAIClient()
    async_openai_client = MockAsyncOpenAIClient()

mock_responses = [
    (
        {
            'messages': [
                {'role': "user", 'content': 'Respond with a single word.'}
            ],
            'model': vllm_model_name,
        },
        "foo"
    ),
    (
        {
            'messages': [
                {'role': "user", 'content': 'Respond with a single word.'}
            ],
            'model': vllm_model_name,
            'stream': True
        },
        ["foo", "bar"]
    ),
    (
        {
            'messages': [
                {'role': "user", 'content': 'Respond with a single word.'}
            ],
            'n': 2,
            'model': vllm_model_name,
        },
        ["foo", "bar"]
    ),
    (
        {
            'messages': [{'role': "user", 'content': 'foo?'}],
            'model': vllm_model_name,
            'max_tokens': 10,
            'extra_body': {
            'guided_json': {
                'type': 'object',
                'properties': {
                    'bar': {'type': 'string'}
                }
            },
            }
        },
        '{"foo": "bar"}'
    ),
    (
        {
            'messages': [{'role': "user", 'content': 'foo?'}],
            'model': vllm_model_name,
            'max_tokens': 10,
            'extra_body': {
                'guided_regex': '([0-9]{3})',
            },
        },
        "123"
    ),
    (
        {
            'messages': [{'role': "user", 'content': 'foo?'}],
            'model': vllm_model_name,
            'max_tokens': 10,
            'extra_body': {
                'guided_grammar': YES_NO_GRAMMAR,
            },
        },
        "yes"
    ),
]


# If the VLLM_SERVER_URL environment variable is not set, add the mock
# responses to the mock clients
if not vllm_server_url:
    async_openai_client.add_mock_responses(mock_responses)
    openai_client.add_mock_responses(mock_responses)


@pytest.fixture
def sync_model():
    return VLLM(openai_client, model_name=vllm_model_name)


@pytest.fixture
def async_model():
    return AsyncVLLM(async_openai_client, model_name=vllm_model_name)


def test_vllm_init():
    model = from_vllm(OpenAI(base_url="http://localhost:11434"))
    assert isinstance(model, VLLM)

    model = from_vllm(AsyncOpenAI(base_url="http://localhost:11434"))
    assert isinstance(model, AsyncVLLM)

    with pytest.raises(ValueError, match="Unsupported client type"):
        from_vllm("foo")


def test_vllm_sync_simple_call(sync_model):
    result = sync_model("Respond with a single word.",)
    assert isinstance(result, str)


def test_vllm_sync_streaming(sync_model):
    result = sync_model.stream("Respond with a single word.")
    assert isinstance(result, Generator)
    assert isinstance(next(result), str)


def test_vllm_sync_multiple_samples(sync_model):
    result = sync_model("Respond with a single word.", n=2)
    assert isinstance(result, list)
    assert len(result) == 2
    assert isinstance(result[0], str)
    assert isinstance(result[1], str)


def test_vllm_sync_json(sync_model):
    json_string = '{"type": "object", "properties": {"bar": {"type": "string"}}}'
    result = sync_model("foo?", JsonSchema(json_string), max_tokens=10)
    assert isinstance(result, str)
    assert "bar" in result


def test_vllm_sync_regex(sync_model):
    result = sync_model("foo?", Regex(r"[0-9]{3}"), max_tokens=10)
    assert isinstance(result, str)
    assert re.match(r"[0-9]{3}", result)


def test_vllm_sync_cfg(sync_model):
    result = sync_model("foo?", CFG(YES_NO_GRAMMAR), max_tokens=10)
    assert isinstance(result, str)
    assert result in ["yes", "no"]


@pytest.mark.asyncio
async def test_vllm_async_simple_call(async_model):
    result = await async_model("Respond with a single word.",)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_vllm_async_streaming(async_model):
    result = async_model.stream("Respond with a single word.")
    assert isinstance(result, AsyncGenerator)
    async for chunk in result:
        assert isinstance(chunk, str)
        break  # Just check the first chunk


@pytest.mark.asyncio
async def test_vllm_async_multiple_samples(async_model):
    result = await async_model("Respond with a single word.", n=2)
    assert isinstance(result, list)
    assert len(result) == 2
    assert isinstance(result[0], str)
    assert isinstance(result[1], str)


@pytest.mark.asyncio
async def test_vllm_async_json(async_model):
    json_string = '{"type": "object", "properties": {"bar": {"type": "string"}}}'
    result = await async_model("foo?", JsonSchema(json_string), max_tokens=10)
    assert isinstance(result, str)
    assert "bar" in result


@pytest.mark.asyncio
async def test_vllm_async_regex(async_model):
    result = await async_model("foo?", Regex(r"[0-9]{3}"), max_tokens=10)
    assert isinstance(result, str)
    assert re.match(r"[0-9]{3}", result)


@pytest.mark.asyncio
async def test_vllm_async_cfg(async_model):
    result = await async_model("foo?", CFG(YES_NO_GRAMMAR), max_tokens=10)
    assert isinstance(result, str)
    assert result in ["yes", "no"]
