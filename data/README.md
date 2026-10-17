# Application data

No demo knowledge documents or evaluation answers are bundled. Upload your own documents through the Knowledge Library.

To enable evaluations, supply a private `data/evaluation.json` containing a nonempty JSON array. Each item requires `question` and `expected_answer` strings, an `expected_documents` list of uploaded filenames, and an `expected_citations` list of objects with `document` and `section` strings. Index the referenced documents before running evaluations. Deploy this file separately; it is ignored by Git. Dataset content determines the comparison version so unrelated benchmarks are not compared.

Without a dataset, the API returns a clear configuration message without recording an empty successful evaluation.
