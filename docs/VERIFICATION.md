# Verification results

Verified locally on Linux using Python **3.12.13**, plus a clean installed-wheel environment
on Python **3.10.20** with the minimum supported runtime dependency versions.

| Check | Result |
| --- | --- |
| `pytest -q` (Python 3.12, including Streamlit) | **63 passed** |
| Installed-wheel tests (Python 3.10, minimum dependencies) | **62 passed, 1 skipped**; optional Streamlit is not installed |
| `ruff check .` | **All checks passed** |
| `python -m compileall -q src app.py` | Passed |
| `ecommerce-kg demo --output docs/sample_results.json` | All ten questions executed successfully |
| `ecommerce-kg query docs/example_query.json --json` | Retrieved exactly five products with the stored keyword |
| Graph invariant | **34 nodes, 67 edges, exactly 5 whole-word banana values** |
| Streamlit AppTest | Graph counts, keyword retrieval and evidence graph view passed |
| OpenAI SDK integration | Both structured calls and retrieved-evidence payload verified using mocked HTTP |
| `uv build` | Wheel and source distribution built successfully |
| Clean wheel installation | Bundled dataset and CLI execute from outside the source directory |
| Source-distribution contents | UI, docs, environment template, tests and `conftest.py` included |

Minimum-dependency check used **NetworkX 3.4**, **Pydantic 2.10.0**, **OpenAI 1.68.0**,
**python-dotenv 1.0.0** and **pytest 8.0.0**. The package was installed from its built wheel;
the test process imported the installed package rather than the editable checkout.

## Code-review fixes and regression coverage

The original suite passed 48 tests. New focused checks reproduced ten failures across
retrieval, dataset validation, LLM error handling and visualization before the fixes.
The complete updated suite passes all 63 tests.

- **Optional-property filtering:** `keyword ne banana` now includes the seven products
  that have no keyword, instead of incorrectly returning no products.
- **Sorting:** absent properties sort last in both directions, including limited and
  multi-key queries.
- **Dataset text/IDs:** surrounding whitespace is normalized, whitespace-only values
  are rejected, and case-insensitive duplicate IDs cannot make query lookup ambiguous.
- **LLM responses:** malformed JSON/schema responses and empty completion choices
  produce controlled backend errors rather than raw validation errors or an `IndexError`.
- **LLM query instructions:** quantities are explicitly unscaled item counts; only
  monetary fields use cents. Edge-property types are included in the supplied schema.
  Requests use the model's default temperature to avoid unsupported-parameter errors.
- **Evidence visualization:** the last-answer view displays only source relationships
  actually retrieved for that answer, rather than every edge between the source nodes.
- **Distribution completeness:** `MANIFEST.in` includes the UI, documentation, environment
  template and test fixtures that setuptools' default source archive omitted.

Additional checks confirm ISO date ranges, case-insensitive text search, exact match-budget
boundaries and historical order totals after catalog prices change. All ten saved sample
results were regenerated and remain consistent with their documented answers.

## Verified graph facts

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
