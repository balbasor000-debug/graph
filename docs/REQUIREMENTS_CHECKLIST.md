# Assignment completion checklist

## Objective and technical requirements

| Requirement | Status | Implementation/evidence |
| --- | --- | --- |
| Simple e-commerce knowledge graph with AI retrieval | Done | Directed NetworkX graph, retrieval service, two-stage live LLM flow |
| Use Python | Done | Installable Python package, CLI, Streamlit UI and tests |
| Use Neo4j or NetworkX | Done | NetworkX `DiGraph`; no external database setup required |
| Products, Brands, Categories, Vendors, Orders, Customers | Done | All six entity kinds; 34 sample nodes |
| Define entity relationships | Done | Six directed relationship types; 67 sample edges |
| Answer questions from the graph | Done | Validated pattern matching, filters, multi-hop retrieval, counts and sums |
| LLM converts natural language into graph queries | Done | OpenAI and Groq backends return structured `QueryDecision`/`QueryPlan` objects |
| User question → LLM → graph query → retrieve → LLM → answer | Done | `RetrievalService.ask()`, provider query planning, NetworkX execution, provider answer planning and evidence rendering |
| Answers based only on retrieved graph data | Done | Only retrieved values/aggregates are rendered; evidence IDs must match; free-form LLM factual text is not accepted |
| Word `banana` appears exactly five times in the graph | Done | Single `keyword: banana` value on each of P004–P008; whole-graph value scan enforces exactly five occurrences |
| Word is retrievable | Done | Product keyword list/count questions and direct JSON query; live Groq listing returns the five stored keyword values |

## Deliverables

| Deliverable | Status | Location |
| --- | --- | --- |
| Working Python project | Done | Repository root, `src/ecommerce_kg/`, `app.py`, `pyproject.toml` |
| Sample e-commerce dataset | Done | [`src/ecommerce_kg/data/ecommerce.json`](../src/ecommerce_kg/data/ecommerce.json) |
| Knowledge graph implementation | Done | [`graph.py`](../src/ecommerce_kg/graph.py), [`schema.py`](../src/ecommerce_kg/schema.py) |
| Retrieval system | Done | [`query.py`](../src/ecommerce_kg/query.py), [`retrieval.py`](../src/ecommerce_kg/retrieval.py), [`service.py`](../src/ecommerce_kg/service.py) |
| LLM integration | Done | [`llm.py`](../src/ecommerce_kg/llm.py); Groq/OpenAI selectable in CLI and UI |
| At least five sample questions with results | Done | Ten offline results in [`sample_results.json`](sample_results.json); live Groq results in [`groq_sample_results.json`](groq_sample_results.json) |
| Complete README setup/execution instructions | Done | [`README.md`](../README.md), including provider configuration, CLI/UI, schema, grounding and tests |
| Loom video | **User recording pending** | [`LOOM_WALKTHROUGH.md`](LOOM_WALKTHROUGH.md) covers every requested topic; publish the video and add its URL to README |

## Verification scope

- Regression tests include graph correctness, malformed query rejection, grounding, both
  provider HTTP integrations, and UI backend selection. See [`VERIFICATION.md`](VERIFICATION.md).
- Groq uses its OpenAI-compatible API with `openai/gpt-oss-20b` and strict JSON-schema output.
  The supplied key is configured only in the ignored local `.env`; published templates have
  empty key fields.
- All ten sample questions were completed through the real Groq API and checked against
  independent expected graph facts. An additional question outside the offline fixtures,
  “Which vendors supply products in Groceries?”, returned Vendor Y and Orchard Supply;
  its query and evidence are in [`groq_additional_result.json`](groq_additional_result.json).
- OpenAI integration remains available with an OpenAI key. Its HTTP tests are mocked;
  the actual live-provider demonstration uses Groq.
- A recorded Loom video is the only unfinished assignment deliverable. The recording should
  show the live provider selection, generated query, retrieved evidence, graph structure,
  banana list/count and a short working demonstration.
