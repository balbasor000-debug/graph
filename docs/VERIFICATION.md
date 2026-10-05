# Verification results

Verified locally on Linux using Python **3.12.13**.

| Check | Result |
| --- | --- |
| `pytest -q` | **48 passed** |
| `ruff check .` | **All checks passed** |
| `python -m compileall -q src app.py` | Passed |
| `ecommerce-kg demo --output docs/sample_results.json` | All ten questions executed successfully |
| `ecommerce-kg query docs/example_query.json --json` | Retrieved exactly five products with the stored keyword |
| Graph invariant | **34 nodes, 67 edges, exactly 5 whole-word banana values** |
| Streamlit AppTest | Graph counts, keyword retrieval and evidence graph view passed |
| OpenAI SDK integration | Both structured calls and retrieved-evidence payload verified using mocked HTTP |

Notable verified facts:

- Brand X + Vendor Y returns P001, P002, P003 and P011.
- Keyword retrieval returns P004, P005, P006, P007 and P008, each with `keyword: banana`.
- Delivered orders total **30996 cents = USD 309.96**.
- Aggregating order totals through an order/product join does not double count orders.
- Deduplicated customer rows retain all supporting order/product relationships.
- Invalid graph patterns and fabricated/missing/duplicated/reordered evidence IDs are rejected.
- Exporting and reloading the graph preserves the five-occurrence invariant.

**Live OpenAI status:** not executed here; no API key is configured. The included integration
verification uses the real OpenAI SDK with an HTTP mock. Use the README's `--mode openai`
instructions to run against your own account.

**Loom status:** no recording/link produced in this environment. Follow
[`LOOM_WALKTHROUGH.md`](LOOM_WALKTHROUGH.md) to record and publish the required video.
