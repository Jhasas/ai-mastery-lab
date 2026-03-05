# Sessao 6 - RAG Query Pipeline

## Contexto

**Projeto**: ai-mastery-lab - Agente bancario com IA
**Fase**: 2 (RAG Pipeline) - FINALIZACAO
**Passo**: 2.6
**Pre-requisito**: Sessao 5 completa (Document model, embedding, chunking, ingestao)
**Modo**: Pair programming - orientar, NAO alterar codigo
**Referencia teorica**: `docs/rag.md` (Bloco 10) - Fase 2 Query

## Objetivo

Implementar a fase de query do RAG: retriever, servico de orquestracao, router, e testes com respx mockando a API do Gemini. Ao final, o endpoint `POST /rag/query` recebe uma pergunta e retorna uma resposta baseada nos documentos bancarios ingeridos.

---

## Passo 2.6 - Retriever, RAG Service e Router

### app/rag/retriever.py

Componente que conecta embedding + vector search:

```python
class Retriever:
    def __init__(self, embedding_client: EmbeddingClient, document_repo: DocumentRepository):
        self.embedding_client = embedding_client
        self.document_repo = document_repo

    async def retrieve(self, question: str, top_k: int = 5) -> list[Document]:
        """Busca os K chunks mais relevantes para a pergunta.

        Pipeline:
        1. Converte pergunta em embedding (mesmo espaco vetorial dos docs)
        2. Busca chunks mais proximos via cosine similarity no pgvector
        """
        start = time.time()

        # Embed a pergunta
        query_embedding = await self.embedding_client.embed(question)

        # Buscar chunks similares
        documents = await self.document_repo.similarity_search(query_embedding, top_k)

        elapsed = (time.time() - start) * 1000
        logger.info("retrieval_complete",
            question=question[:50], top_k=top_k,
            results_found=len(documents), elapsed_ms=round(elapsed, 2)
        )

        return documents
```

### app/services/rag_service.py

Orquestracao completa do pipeline RAG (conforme `docs/rag.md` - passos 5 a 9):

```python
class RagService:
    def __init__(self, retriever: Retriever, settings: Settings):
        self.retriever = retriever
        self.settings = settings

    async def query(self, request: RagQueryRequest) -> RagQueryResponse:
        """Pipeline RAG completo:
        1. Retrieve: busca chunks relevantes
        2. Augment: monta prompt com contexto
        3. Generate: LLM gera resposta baseada no contexto
        """
        start = time.time()

        # 1. RETRIEVE - busca chunks similares
        documents = await self.retriever.retrieve(request.question, request.top_k)

        if not documents:
            return RagQueryResponse(
                answer="Nao encontrei informacoes relevantes nos documentos do banco.",
                sources=[],
                query_duration_ms=int((time.time() - start) * 1000)
            )

        # 2. AUGMENT - monta prompt com contexto
        context = "\n\n---\n\n".join([doc.content for doc in documents])

        prompt = f"""Voce e um assistente do banco. Responda APENAS com base no contexto abaixo.
Se nao encontrar a informacao no contexto, diga "Nao encontrei essa informacao nos documentos do banco."

CONTEXTO:
{context}

PERGUNTA: {request.question}

RESPOSTA:"""

        # 3. GENERATE - chama LLM
        answer = await self._call_llm(prompt)

        elapsed = int((time.time() - start) * 1000)

        return RagQueryResponse(
            answer=answer,
            sources=[DocumentResponse.model_validate(doc) for doc in documents],
            query_duration_ms=elapsed
        )

    async def _call_llm(self, prompt: str) -> str:
        """Chama Gemini para gerar resposta."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model}:generateContent"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                params={"key": self.settings.gemini_api_key},
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
```

**Design decisions**:
- Usar `httpx` diretamente (nao LangChain) para `_call_llm` nesta fase. Na Fase 3, o agente usara LangChain/LangGraph.
- Isso facilita mock com `respx` nos testes.
- O prompt e fixo e claro: "responda APENAS com base no contexto".

### app/routers/rag_router.py

```python
router = APIRouter(prefix="/rag", tags=["RAG"])

async def get_rag_service(db: AsyncSession = Depends(get_db)) -> RagService:
    settings = get_settings()
    embedding_client = EmbeddingClient(settings.gemini_api_key, settings.gemini_embedding_model)
    document_repo = DocumentRepository(db)
    retriever = Retriever(embedding_client, document_repo)
    return RagService(retriever, settings)

@router.post("/query", response_model=RagQueryResponse)
async def query_rag(
    request: RagQueryRequest,
    service: RagService = Depends(get_rag_service)
):
    return await service.query(request)
```

### Atualizar app/main.py

```python
from app.routers import rag_router
app.include_router(rag_router.router)
```

---

## Testes

### tests/fixtures/__init__.py e tests/fixtures/llm_responses.py

Mock responses pre-construidas para o Gemini API:

```python
# Embedding response
EMBEDDING_RESPONSE = {
    "embedding": {
        "values": [0.1] * 768  # vetor de 768 dimensoes
    }
}

# Chat/Generation response
CHAT_RESPONSE = {
    "candidates": [{
        "content": {
            "parts": [{
                "text": "O limite de PIX noturno e de R$ 1.000,00 por transacao."
            }]
        }
    }]
}

# Chat response when no relevant context
NO_INFO_RESPONSE = {
    "candidates": [{
        "content": {
            "parts": [{
                "text": "Nao encontrei essa informacao nos documentos do banco."
            }]
        }
    }]
}
```

### tests/unit/test_rag_service.py

Mock `Retriever` e `_call_llm`:

| Teste | Cenario | Mock | Assertacao |
|-------|---------|------|-----------|
| `test_should_return_answer_with_sources` | Pergunta com docs encontrados | Retriever retorna 3 docs, LLM retorna resposta | answer preenchido, 3 sources |
| `test_should_include_context_in_prompt` | Verificar que prompt contem contexto | Capturar argumento de _call_llm | Conteudo dos docs no prompt |
| `test_should_return_no_results_when_no_documents` | Nenhum doc encontrado | Retriever retorna [] | "Nao encontrei", sources vazio |
| `test_should_include_query_duration` | Qualquer query | - | query_duration_ms > 0 |

### tests/integration/test_rag_router.py

Testes end-to-end com Testcontainers + respx:

**Setup**: No conftest.py ou setup do teste:
1. Criar tabela documents no Testcontainers PostgreSQL
2. Inserir 3-5 documentos com embeddings fixos (vetores conhecidos)
3. Configurar `respx` para interceptar chamadas ao Gemini API

**Mocking com respx**:
```python
import respx

@pytest.fixture
def mock_gemini():
    with respx.mock:
        # Mock embedding endpoint
        respx.post(
            url__startswith="https://generativelanguage.googleapis.com/v1beta/models/embedding"
        ).mock(return_value=httpx.Response(200, json=EMBEDDING_RESPONSE))

        # Mock generation endpoint
        respx.post(
            url__startswith="https://generativelanguage.googleapis.com/v1beta/models/gemini"
        ).mock(return_value=httpx.Response(200, json=CHAT_RESPONSE))

        yield
```

| Teste | Setup | Request | Assertacao |
|-------|-------|---------|-----------|
| `test_should_return_200_with_answer_and_sources` | Docs no banco + mock Gemini | POST /rag/query {"question": "Qual o limite do PIX?"} | 200, answer preenchido, sources nao vazio |
| `test_should_return_422_when_question_too_short` | - | POST /rag/query {"question": "ab"} | 422, validation error |
| `test_should_return_answer_even_with_no_documents` | Banco vazio + mock Gemini | POST /rag/query | 200, "Nao encontrei" |

### Atualizar tests/conftest.py

Adicionar:
- Extension pgvector habilitada no Testcontainers: `await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))`
- Fixture para inserir documentos de teste com embeddings conhecidos
- Fixture `mock_gemini` reutilizavel

---

## Validacao da Sessao

```bash
# Testes
pytest tests/ -v
# Todos devem passar (unit + integration, RAG + Account + Transaction)

# Teste manual (precisa de GEMINI_API_KEY real)
uvicorn app.main:app --reload

# 1. Ingerir docs (se ainda nao fez na sessao 5)
python scripts/ingest.py

# 2. Fazer query RAG
curl -X POST http://localhost:8000/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Qual o limite do PIX noturno?", "top_k": 3}'

# Resposta deve conter informacao do data/policies/pix.md
```

---

## Entrega da Sessao 6 (Fase 2 COMPLETA)

Ao final, alem do que ja existia:
```
app/
├── rag/
│   └── retriever.py            # NOVO
├── services/
│   └── rag_service.py          # NOVO
├── routers/
│   └── rag_router.py           # NOVO
tests/
├── fixtures/
│   ├── __init__.py             # NOVO
│   └── llm_responses.py        # NOVO
├── unit/
│   └── test_rag_service.py     # NOVO
├── integration/
│   └── test_rag_router.py      # NOVO
```

**Fase 2 completa**. O pipeline RAG esta funcional:
- Ingestao: markdown → chunks → embeddings → pgvector
- Query: pergunta → embed → similarity search → prompt com contexto → LLM → resposta
- Testes mockam Gemini API com respx (nao precisa de API key para rodar testes)
