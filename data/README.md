# Application data

The eight synthetic SaiTech knowledge documents are kept in `data/demo/`. They are demonstration policies, not real company policies. Upload and process them through the Knowledge Library to enable the demo answers. Upload your own documents when replacing the demo content. No evaluation answers are bundled.

To enable evaluations, supply a private `data/evaluation.json` containing a nonempty JSON array. Each item requires `question` and `expected_answer` strings, an `expected_documents` list of uploaded filenames, and an `expected_citations` list of objects with `document` and `section` strings. Index the referenced documents before running evaluations. Deploy this file separately; it is ignored by Git. Dataset content determines the comparison version so unrelated benchmarks are not compared.

Without a dataset, the API returns a clear configuration message without recording an empty successful evaluation.
