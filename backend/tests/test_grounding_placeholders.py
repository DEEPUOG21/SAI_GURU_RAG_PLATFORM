from app.services.grounding import check_grounding


async def test_citations_cannot_replace_requested_values():
    class Judge:
        async def complete(self, *args, **kwargs):
            raise AssertionError("Malformed factual answer reached model judge")

    verdict, _ = await check_grounding(
        Judge(),
        "What is the approved budget?",
        "The approved budget is [Source 1] INR.",
        [{"label": "Source 1", "text": "The approved budget is 44000 INR."}],
    )
    assert verdict["status"] == "UNSUPPORTED"
