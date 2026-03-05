# Sessao 5 - RAG Ingestion Pipeline

## Contexto

**Projeto**: ai-mastery-lab - Agente bancario com IA
**Fase**: 2 (RAG Pipeline)
**Passos**: 2.1 a 2.5
**Pre-requisito**: Sessao 4 completa (Fase 1 finalizada - API bancaria funcional)
**Modo**: Pair programming - orientar, NAO alterar codigo
**Referencia teorica**: `docs/rag.md` (Bloco 10)

## Objetivo

Implementar a fase de ingestao do RAG pipeline: criar o modelo Document com pgvector, embedding client, chunking, e script de ingestao. Ao final, documentos de politica bancaria estarao armazenados como chunks vetorizados no PostgreSQL.

---

## Passo 2.1 - Document Model com pgvector

### app/models/document.py

Modelo SQLAlchemy com coluna de embedding vetorial:

```python
from pgvector.sqlalchemy import Vector

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(nullable=False)         # nome do documento fonte
    content: Mapped[str] = mapped_column(Text, nullable=False) # texto do chunk
    embedding = mapped_column(Vector(768))                      # vetor 768 dimensoes (Gemini)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True                         # chunk_index, source, etc.
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now()
    )
```

**IMPORTANTE**: O campo `metadata_` usa alias `"metadata"` na coluna porque `metadata` e reservado no SQLAlchemy.

**Atualizar** `app/models/__init__.py` para importar Document.

### app/schemas/document.py

**DocumentResponse(BaseModel)**:
- `id: int`
- `title: str`
- `content: str`
- `metadata_: dict | None` (alias "metadata")
- `created_at: datetime`
- SEM embedding (muito grande para response JSON)
- `model_config = ConfigDict(from_attributes=True)`

### app/schemas/rag.py

**RagQueryRequest(BaseModel)**:
- `question: str = Field(min_length=3)` (pergunta do usuario)
- `top_k: int = Field(default=5, ge=1, le=20)` (quantos chunks retornar)

**RagQueryResponse(BaseModel)**:
- `answer: str` (resposta gerada pelo LLM)
- `sources: list[DocumentResponse]` (chunks usados como contexto)
- `query_duration_ms: int` (tempo total da query)

### Alembic migration

```bash
alembic revision --autogenerate -m "create documents table with pgvector"
```

**IMPORTANTE**: Antes do CREATE TABLE, a migration precisa:
```python
def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # ... create table com coluna embedding vector(768)
```

Apos criar a tabela, criar indice IVFFlat para busca rapida:
```python
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_embedding
        ON documents
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
```

```bash
alembic upgrade head
```

---

## Passo 2.2 - Embedding Client

### app/rag/embeddings.py

Wrapper para a API de Embedding do Gemini. Usar `httpx.AsyncClient` diretamente (nao LangChain) para ter controle total e facilitar mock com `respx`.

```python
class EmbeddingClient:
    def __init__(self, api_key: str, model: str = "models/embedding-001"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def embed(self, text: str) -> list[float]:
        """Gera embedding de um texto. Retorna vetor de 768 dimensoes."""
        url = f"{self.base_url}/{self.model}:embedContent"
        payload = {
            "model": self.model,
            "content": {"parts": [{"text": text}]}
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                params={"key": self.api_key},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()["embedding"]["values"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Gera embeddings para multiplos textos."""
        # Chamar embed() para cada texto (ou usar batch API se disponivel)
        results = []
        for text in texts:
            embedding = await self.embed(text)
            results.append(embedding)
        return results
```

Adicionar:
- structlog para logar cada chamada (duracao, modelo usado)
- Retry com backoff para rate limits (status 429)
- Tratamento de erros HTTP

### Teste unitario (opcional neste passo, sera coberto na sessao 6)

Mock com `respx`:
```python
respx.post("https://generativelanguage.googleapis.com/v1beta/models/embedding-001:embedContent").mock(
    return_value=httpx.Response(200, json={"embedding": {"values": [0.1] * 768}})
)
```

---

## Passo 2.3 - Chunking

### app/rag/chunker.py

Usar `RecursiveCharacterTextSplitter` do LangChain (conforme `docs/rag.md` linhas 218-229):

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Configuracao de chunking
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,        # tamanho maximo do chunk em caracteres
    chunk_overlap=50,      # overlap entre chunks para nao perder contexto
    separators=["\n\n", "\n", " ", ""],  # tenta dividir por paragrafo primeiro
)

def chunk_document(title: str, content: str) -> list[dict]:
    """Divide um documento em chunks menores.

    Retorna lista de dicts com:
    - title: nome do documento fonte
    - content: texto do chunk
    - metadata: {"chunk_index": i, "source": title, "total_chunks": N}
    """
    chunks = splitter.split_text(content)
    return [
        {
            "title": title,
            "content": chunk,
            "metadata": {
                "chunk_index": i,
                "source": title,
                "total_chunks": len(chunks),
            }
        }
        for i, chunk in enumerate(chunks)
    ]
```

**Parametros de chunking**:
- `chunk_size=500`: sweet spot para documentos bancarios (nao muito grande, nao muito pequeno)
- `chunk_overlap=50`: 10% de overlap evita perder contexto na fronteira entre chunks
- `separators`: tenta manter paragrafos inteiros, depois linhas, depois palavras

### data/policies/ - Documentos de politica bancaria

Criar 4 arquivos markdown com conteudo ficticio mas realista de um banco:

**data/policies/pix.md** (~600 palavras):
- O que e PIX
- Horarios de funcionamento (24/7)
- Limites de transferencia (diurno R$ 20.000, noturno R$ 1.000)
- Chaves PIX (CPF, email, celular, aleatoria)
- Regras de seguranca
- Devolucao/estorno (MED)

**data/policies/transfers.md** (~500 palavras):
- TED: horario comercial, sem limite minimo, liquidacao no mesmo dia
- DOC: liquidacao D+1, valores menores
- Transferencia entre contas do mesmo banco: instantanea, sem custo
- Limites por tipo de conta

**data/policies/account_types.md** (~400 palavras):
- Conta Corrente: sem limite de transacoes, taxa mensal
- Conta Poupanca: rendimento mensal, limite de transacoes
- Conta Salario: recebimento de salario, portabilidade
- Conta Digital: sem taxa, totalmente online

**data/policies/fees.md** (~400 palavras):
- Tarifas de manutencao por tipo de conta
- Tarifas de transferencia (TED, DOC, PIX)
- Tarifas de cartao de credito
- Pacotes de servicos
- Isencoes (conta digital, renda acima de X)

---

## Passo 2.4 - Document Repository (Vector Search)

### app/repositories/document_repository.py

Repository com capacidade de busca vetorial:

| Metodo | Descricao |
|--------|-----------|
| `store(title, content, embedding, metadata)` | Persiste chunk com vetor |
| `store_batch(documents: list)` | Persiste multiplos chunks de uma vez |
| `similarity_search(query_embedding, top_k=5)` | Busca os K chunks mais similares por cosine distance |
| `delete_by_title(title)` | Deleta todos os chunks de um documento (para re-ingestao) |
| `count()` | Total de chunks no banco |

**similarity_search** usa o operador `<=>` do pgvector (cosine distance):

```python
async def similarity_search(
    self, query_embedding: list[float], top_k: int = 5
) -> list[Document]:
    stmt = (
        select(Document)
        .order_by(Document.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    result = await self.session.execute(stmt)
    return list(result.scalars().all())
```

Alternativa com SQL raw (mais explicito):
```sql
SELECT *, embedding <=> :query_vector AS distance
FROM documents
ORDER BY distance
LIMIT :top_k
```

---

## Passo 2.5 - Script de Ingestao

### scripts/ingest.py

Script CLI que implementa o pipeline de ingestao completo (conforme `docs/rag.md` - Fase 1):

```
Documentos (.md)  →  Chunking  →  Embedding  →  Store (pgvector)
```

Fluxo:
1. Ler todos os `.md` de `data/policies/`
2. Para cada arquivo:
   a. Ler conteudo
   b. Chunk com `chunk_document()`
   c. Para cada chunk: gerar embedding com `EmbeddingClient.embed()`
   d. Persistir no banco com `DocumentRepository.store()`
3. Logar progresso (total docs, total chunks, duracao)

**Idempotencia**: antes de ingerir um documento, deletar chunks existentes com mesmo title:
```python
await document_repo.delete_by_title(title)
```

```python
# scripts/ingest.py
import asyncio
from pathlib import Path

async def ingest():
    logger.info("starting_ingestion")

    policies_dir = Path("data/policies")
    files = list(policies_dir.glob("*.md"))

    total_chunks = 0
    for file in files:
        title = file.stem  # "pix", "transfers", etc.
        content = file.read_text()

        # 1. Chunk
        chunks = chunk_document(title, content)

        # 2. Delete existing (idempotencia)
        await document_repo.delete_by_title(title)

        # 3. Embed + Store
        for chunk_data in chunks:
            embedding = await embedding_client.embed(chunk_data["content"])
            await document_repo.store(
                title=chunk_data["title"],
                content=chunk_data["content"],
                embedding=embedding,
                metadata=chunk_data["metadata"]
            )

        total_chunks += len(chunks)
        logger.info("document_ingested", title=title, chunks=len(chunks))

    logger.info("ingestion_complete", total_files=len(files), total_chunks=total_chunks)

if __name__ == "__main__":
    asyncio.run(ingest())
```

### Validacao

```bash
# Subir Postgres
docker compose up -d postgres-lab

# Rodar migrations
alembic upgrade head

# Executar ingestao (precisa de GEMINI_API_KEY no .env)
python scripts/ingest.py

# Verificar no banco
# psql -h localhost -p 5433 -U postgres -d ai_mastery_lab
# SELECT title, LEFT(content, 80), array_length(embedding, 1) FROM documents LIMIT 5;
```

**Para testes sem API key**: criar um modo "mock" que gera embeddings aleatorios:
```python
if settings.environment == "test":
    embedding = [random.random() for _ in range(768)]
else:
    embedding = await embedding_client.embed(text)
```

---

## Entrega da Sessao 5

Ao final, alem do que ja existia:
```
app/
├── models/
│   └── document.py             # NOVO
├── schemas/
│   ├── document.py             # NOVO
│   └── rag.py                  # NOVO
├── repositories/
│   └── document_repository.py  # NOVO
├── rag/
│   ├── __init__.py             # NOVO
│   ├── embeddings.py           # NOVO
│   └── chunker.py              # NOVO
scripts/
│   └── ingest.py               # NOVO
data/policies/
│   ├── pix.md                  # NOVO
│   ├── transfers.md            # NOVO
│   ├── account_types.md        # NOVO
│   └── fees.md                 # NOVO
alembic/versions/
│   └── 002_documents_pgvector.py  # NOVO
```

Deve ser possivel:
- `python scripts/ingest.py` → documentos ingeridos no pgvector
- Verificar no banco que chunks tem embeddings de 768 dimensoes
- Chunking divide documentos de 500+ caracteres em pedacos menores com overlap
