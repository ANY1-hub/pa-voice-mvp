from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.embeddings.openai import OpenAIEmbeddingsAdapter
from src.services.llm.gemini import GeminiLLMAdapter
from src.services.llm.grok import GrokLLMAdapter
from src.services.llm.openai import OpenAILLMAdapter


@pytest.mark.asyncio
async def test_openai_embeddings_adapter():
    """OpenAI embeddings adapter must return single and batch vectors from the API mock."""
    with patch("src.services.embeddings.openai.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client

        # Mock embedding response
        mock_response = MagicMock()
        mock_item1 = MagicMock()
        mock_item1.embedding = [0.1, 0.2, 0.3]
        mock_item2 = MagicMock()
        mock_item2.embedding = [0.4, 0.5, 0.6]
        mock_response.data = [mock_item1, mock_item2]

        mock_client.embeddings.create.return_value = mock_response

        adapter = OpenAIEmbeddingsAdapter(api_key="test_key")

        single_embedding = await adapter.get_embedding("test")
        assert single_embedding == [0.1, 0.2, 0.3]

        multi_embedding = await adapter.get_embeddings(["test1", "test2"])
        assert multi_embedding == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


@pytest.mark.asyncio
async def test_openai_llm_adapter_generate_response():
    """OpenAI LLM adapter must return the assistant message content."""
    with patch("src.services.llm.openai.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client

        # Mock chat response
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello there!"
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        adapter = OpenAILLMAdapter(api_key="test_key")
        response = await adapter.generate_response([{"role": "user", "content": "Hi"}])
        assert response == "Hello there!"


@pytest.mark.asyncio
async def test_openai_llm_adapter_extract_entities():
    """Entity extraction must parse JSON entities and fall back to [] on bad JSON."""
    with patch("src.services.llm.openai.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client

        # Mock JSON extraction
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"entities": ["Python", "OpenAI"]}'
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        adapter = OpenAILLMAdapter(api_key="test_key")
        entities = await adapter.extract_entities("I like Python and OpenAI")
        assert entities == ["Python", "OpenAI"]

        # Test JSON decode error handling
        mock_choice.message.content = "invalid json"
        entities_fallback = await adapter.extract_entities("something")
        assert entities_fallback == []


@pytest.mark.asyncio
async def test_grok_llm_adapter_generate_response():
    """Grok adapter must call the xAI base URL and return the message content."""
    with patch("src.services.llm.grok.AsyncOpenAI") as mock_grok:
        mock_client = AsyncMock()
        mock_grok.return_value = mock_client

        # Mock chat response
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Grok response!"
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        adapter = GrokLLMAdapter(api_key="test_key")
        response = await adapter.generate_response([{"role": "user", "content": "Hi"}])
        assert response == "Grok response!"

        # Verify it uses the right base URL via kwargs to AsyncOpenAI constructor
        mock_grok.assert_called_with(api_key="test_key", base_url="https://api.x.ai/v1")


@pytest.mark.asyncio
async def test_grok_llm_adapter_extract_entities():
    """Grok entity extraction must parse the JSON entities list."""
    with patch("src.services.llm.grok.AsyncOpenAI") as mock_grok:
        mock_client = AsyncMock()
        mock_grok.return_value = mock_client

        # Mock JSON extraction
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"entities": ["Grok", "SpaceX"]}'
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        adapter = GrokLLMAdapter(api_key="test_key")
        entities = await adapter.extract_entities("I like Grok and SpaceX")
        assert entities == ["Grok", "SpaceX"]


@pytest.mark.asyncio
async def test_gemini_llm_adapter_not_implemented():
    """Gemini stub must raise NotImplementedError until wired."""
    adapter = GeminiLLMAdapter(api_key="test_key")

    with pytest.raises(NotImplementedError):
        await adapter.generate_response([{"role": "user", "content": "Hi"}])

    with pytest.raises(NotImplementedError):
        await adapter.extract_entities("test")
