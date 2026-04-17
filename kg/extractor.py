import json
import re
import requests
from typing import Any, Dict, List

_PROMPT = """\
Проаналізуй повідомлення від "{sender}" в чаті "{chat}".

Повідомлення:
\"\"\"{text}\"\"\"

Витягни значущі дані. Поверни JSON масив де кожен елемент має:
- "type": "fact" | "intent" | "emotion" | "behavior"
- "value": короткий опис українською (до 1 речення)
- "confidence": 0.0–1.0

Типи:
  fact      — конкретний факт про людину або ситуацію
  intent    — чого хоче / прагне людина
  emotion   — емоційний стан у цьому повідомленні
  behavior  — характерна поведінкова риса (лише якщо очевидно)

Якщо немає нічого значущого — поверни [].
Відповідай ТІЛЬКИ JSON масивом, без пояснень."""


def extract(
    text: str,
    sender: str,
    chat: str,
    llm_url: str,
    llm_model: str,
) -> List[Dict[str, Any]]:
    prompt = _PROMPT.format(sender=sender, chat=chat, text=text.strip())
    try:
        resp = requests.post(
            llm_url,
            json={
                "model": llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 512,
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()

        # Strip markdown code fences if present
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", content)
        raw = match.group(1) if match else content

        # Try to parse JSON
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[Extractor] JSON parse error: {e}")
            print(f"[Extractor] Raw content: {raw[:200]}...")
            # Try to fix common JSON issues
            # Try to extract array from the content
            array_match = re.search(r"\[[\s\S]*\]", raw)
            if array_match:
                try:
                    items = json.loads(array_match.group(0))
                except json.JSONDecodeError:
                    print(f"[Extractor] Could not fix JSON")
                    return []
            else:
                return []

        if not isinstance(items, list):
            print(f"[Extractor] Expected list, got {type(items)}")
            return []
        return [
            i for i in items
            if isinstance(i, dict)
            and i.get("type") in ("fact", "intent", "emotion", "behavior")
            and isinstance(i.get("value"), str)
            and i["value"].strip()
        ]
    except Exception as e:
        print(f"[Extractor] Error: {e}")
        import traceback
        traceback.print_exc()
        return []
