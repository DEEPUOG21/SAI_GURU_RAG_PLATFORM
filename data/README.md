# Application data

The eight synthetic SaiTech knowledge documents are kept in `data/demo/`. They are demonstration policies, not real company policies. Upload and process them through the Knowledge Library to enable the demo answers. Upload your own documents when replacing the demo content. The bundled `data/demo/evaluation.json` contains eight labeled demo questions, one per document. The evaluation API uses it by default. These results measure the synthetic demonstration corpus, not production readiness.

To override the demo benchmark, supply a private `data/evaluation.json` containing a nonempty JSON array. Each item requires `question` and `expected_answer` strings, an `expected_documents` list of uploaded filenames, and an `expected_citations` list of objects with `document` and `section` strings. Index the referenced documents before running evaluations. Deploy this file separately; it is ignored by Git. Dataset content determines the comparison version so unrelated benchmarks are not compared.

If both the private and bundled demo datasets are absent, the API returns a clear configuration message without recording an empty successful evaluation.
