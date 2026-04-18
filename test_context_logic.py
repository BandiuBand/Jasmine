import unittest

from jasmine_filter import decide_response, build_context_window, infer_chat_roles


class ContextLogicTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "jasmine_filter": {
                "bot_name": "Жасмін",
                "bot_name_variations": ["жасмін", "jasmine"],
                "response_coefficients": {
                    "industries": [
                        {"name": "IT", "coefficient": 0.8, "keywords": ["код", "python", "помилка"]}
                    ],
                    "default_coefficient": 0.05,
                },
            }
        }

    def test_decide_response_for_direct_question(self):
        msg = {
            "chat_id": "chat1",
            "date_str": "2026-04-18",
            "timestamp": "12:00:00",
            "text": "Жасмін, допоможи з помилкою в python коді?",
            "sender": "user1",
        }
        should, score, reasons = decide_response(
            msg=msg,
            config=self.config,
            context_state={"chats": {}},
            recent_chat_messages=[msg],
            is_jasmine=True,
            is_question=True,
        )
        self.assertTrue(should)
        self.assertGreaterEqual(score, 0.65)
        self.assertTrue(any("звернення" in r for r in reasons))

    def test_context_window_stays_in_same_chat(self):
        messages = [
            {"chat_id": "a", "text": "поговоримо про python", "date_str": "2026-04-18", "timestamp": "10:00:00", "sender": "u1"},
            {"chat_id": "a", "text": "у мене помилка в коді", "date_str": "2026-04-18", "timestamp": "10:01:00", "sender": "u1"},
            {"chat_id": "b", "text": "інша тема", "date_str": "2026-04-18", "timestamp": "10:02:00", "sender": "u2"},
            {"chat_id": "a", "text": "жасмін, як це фіксити", "date_str": "2026-04-18", "timestamp": "10:03:00", "sender": "u1"},
        ]
        window = build_context_window(messages, 3, max_messages=5)
        self.assertTrue(all(m["chat_id"] == "a" for m in window))
        self.assertGreaterEqual(len(window), 2)

    def test_infer_roles(self):
        messages = [
            {"sender": "jasmine_bot", "text": "Привіт"},
            {"sender": "user1", "text": "Привіт"},
            {"sender": "user1", "text": "Допоможи"},
        ]
        roles = infer_chat_roles(messages, self.config)
        self.assertEqual(roles["jasmine_bot"]["role"], "assistant")
        self.assertEqual(roles["user1"]["role"], "human")


if __name__ == "__main__":
    unittest.main()
