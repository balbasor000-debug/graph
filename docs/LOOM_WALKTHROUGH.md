# Loom walkthrough: ready-to-record script

**Status:** recording still required. No video or published Loom URL has been generated.

## Preparation

1. Follow the README setup and activate `.venv`.
2. Set `GROQ_API_KEY` and `GROQ_MODEL=openai/gpt-oss-20b` in `.env` to demonstrate the tested live LLM flow, or configure OpenAI. Keep `.env` closed and out of the recording.
3. Run `streamlit run app.py`; open the browser page.
4. Open the README, `src/ecommerce_kg/graph.py`, `query.py`, `llm.py`, `service.py` and the sample dataset in your editor.
5. Open Loom's desktop app or browser recorder; select the project browser/editor window and microphone. Record approximately 5–7 minutes.

## 0:00–0:40 — Overall approach

Suggested narration:

> “This is a Python e-commerce knowledge graph with AI-powered retrieval. NetworkX holds a directed property graph, so there is no database-server setup. Groq or OpenAI translates natural-language questions into a typed, read-only graph query. The retriever executes it and returns evidence; a second LLM call chooses the answer presentation, and the application renders only retrieved values.”

Show the README flow diagram and sidebar graph counts.

## 0:40–1:30 — Graph structure and relationships

Show the **Graph explorer** and the README relationship table.

> “There are 34 nodes: 12 products, 3 brands, 4 categories, 3 vendors, 7 orders and 5 customers. The 67 directed relationships represent product brands/categories, vendor supply, customer orders, order contents and fulfillment. Order-item edges carry quantity and historical unit price. We use integer USD cents, and compute order totals from those edges.”

Point out `Customer → PLACED → Order → CONTAINS → Product`, and `Vendor → SUPPLIES → Product → OF_BRAND → Brand`. Explain loader checks for references, vendor compatibility and duplicate IDs.

## 1:30–2:40 — Query process and live LLM integration

Choose **Groq live** (or **OpenAI live** with its own key), ask:

> Which products from Brand X are supplied by Vendor Y?

Click **Retrieve answer**, then expand **Validated graph query** and **Retrieved evidence and relationship provenance**.

> “The first LLM call receives the graph schema and graph-sourced entity catalog. In this demonstration it uses OpenAI's GPT-OSS 20B model hosted by Groq. It returns a structured QueryPlan. Pydantic checks every property, alias, edge direction and type. The retriever filters candidates and traverses the matching relationships. These four rows are Wireless Headphones, Mechanical Keyboard, Ceramic Coffee Mug and Trail Water Bottle.”

Show the two calls in `llm.py` and the schema in `query.py`. Explain that the first call generates JSON rather than executable code, and that traversal has bounded resource budgets.

## 2:40–3:30 — Evidence-only grounding

Show `service.py`, citations in the UI, and one evidence row with source IDs/edges.

> “Grounding is enforced in code. The second LLM call may choose table or bullets and must copy every evidence ID in retrieval order. It cannot provide free-form factual prose. The renderer reads the values from retrieved rows, checks the IDs, and rejects invented or missing citations. Counts and sums are computed from the graph. Empty retrieval returns a fixed no-match message.”

Ask:

> Which products from Brand X are supplied by Orchard Supply?

Show the no-match response. Explain the distinction between no matching data and a question outside the supported schema.

## 3:30–4:20 — Exactly five `banana` occurrences

Ask:

> Which products contain the keyword banana?

Show the five rows, then:

> How many products contain the keyword banana?

Show count **5**, the sidebar metric, and the **banana neighborhood** graph view.

> “The word is stored as a single keyword value on each of P004 through P008. It is not copied onto brands, categories or edges. The graph loader scans every graph/node/edge attribute value for whole-word occurrences and fails unless there are exactly five. Documentation and query output are outside the graph.”

Show the five entries in the dataset and `word_occurrences()` in `graph.py`.

## 4:20–5:20 — Multi-hop queries and numeric aggregates

Ask:

> Which customers have delivered orders containing products with the keyword banana?

Show **Bob Smith** and **Carla Gomez**, with provenance through customers, orders and products.

Ask:

> What is the total value of delivered orders?

Show **USD 309.96**, and the five contributing order IDs.

> “The delivered filter excludes the shipped and cancelled orders. Aggregation happens before row limiting, with distinct-entity semantics to prevent double counting across graph joins.”

## 5:20–6:00 — Reproducibility and tests

Show the README setup commands and ten-row results table. In a terminal, run:

```bash
ecommerce-kg inspect
pytest -q
```

> “The bundled offline mode uses predefined sample plans and still performs real graph retrieval. It is clearly labeled, so it is distinguishable from live LLM mode. The tests verify sample answers, five occurrences, invalid query rejection, deduplication and aggregates, and refusal of fabricated evidence. Mocked HTTP tests verify both providers without needing a key, and the repository also contains actual live Groq results.”

## Finish and submit

1. Stop recording and wait for Loom to publish.
2. Title the recording **E-commerce Knowledge Graph — NetworkX + Groq/OpenAI**.
3. Ensure reviewers can view the link.
4. Replace the Loom URL placeholder in `README.md` and mark its recording status complete.
5. Submit the project directory and the published Loom URL together.

If recording only the offline demonstration, explicitly state that the demonstration uses predefined queries and show the configured live-provider code separately; do not describe offline execution as a live LLM call.
