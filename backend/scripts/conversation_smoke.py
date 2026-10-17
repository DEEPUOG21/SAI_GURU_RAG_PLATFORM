"""Exercise real multi-turn HTTP chat against the running local preview, without printing credentials."""

import json

import httpx
from dotenv import dotenv_values


def main():
    cfg = dotenv_values(".env")
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=330) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": cfg["SEED_ADMIN_EMAIL"], "password": cfg["SEED_ADMIN_PASSWORD"]},
        )
        login.raise_for_status()
        client.headers["Authorization"] = "Bearer " + login.json()["access_token"]

        def ask(question, conversation=None):
            payload = {"question": question}
            if conversation:
                payload["conversation_id"] = conversation
            response = client.post("/api/v1/chat", json=payload)
            response.raise_for_status()
            frames = [
                json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
            ]
            final = next((f for f in frames if "answer" in f), None)
            assert final, response.text
            conversation = next(f["conversation_id"] for f in frames if "conversation_id" in f)
            print(
                json.dumps(
                    {"question": question, "answer": final["answer"], "grounding": final["grounding"]}
                ),
                flush=True,
            )
            return final, conversation

        answer, general = ask("Who is the father of the nation in India?")
        assert "gandhi" in answer["answer"].lower()
        answer, general = ask("When was he born?", general)
        assert "1869" in answer["answer"]
        answer, general = ask("Where was he born?", general)
        assert "porbandar" in answer["answer"].lower()
        answer, documents = ask("How many paid annual leave days do full-time SaiTech employees receive?")
        assert "24" in answer["answer"] and answer["grounding"] == "SUPPORTED"
        answer, documents = ask("How does it accrue?", documents)
        assert answer["citations"] and ("two" in answer["answer"].lower() or "2" in answer["answer"])
        answer, documents = ask("What about contractors?", documents)
        contractor_answer = answer["answer"].lower()
        assert answer["citations"] and "contractor" in contractor_answer
        assert any(
            phrase in contractor_answer
            for phrase in ("agreement", "does not apply", "do not receive", "not eligible")
        )
        answer, documents = ask("What is Python?", documents)
        assert "programming" in answer["answer"].lower() and answer["grounding"] == "NOT_APPLICABLE"
        answer, _ = ask("What is our sabbatical policy?")
        assert answer["grounding"] == "GENERAL_KNOWLEDGE" and not answer["citations"]
        reloaded = client.get(f"/api/v1/conversations/{documents}/messages")
        reloaded.raise_for_status()
        assert reloaded.json()[-1]["grounding"] == "NOT_APPLICABLE"
        print(
            "Multi-turn general knowledge, cited RAG, topic switch, missing-evidence guidance and history reload passed.",
            flush=True,
        )


if __name__ == "__main__":
    main()
