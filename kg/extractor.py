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
    fallback_url: str = None,
    fallback_model: str = None,
) -> List[Dict[str, Any]]:
    prompt = _PROMPT.format(sender=sender, chat=chat, text=text.strip())
    
    # Спроба основного LLM
    try:
        resp = requests.post(
            llm_url,
            json={
                "model": llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 20000,
            },
            timeout=450,
        )
        if not resp.ok:
            print(f"[Extractor] LM Studio HTTP {resp.status_code} body: {resp.text[:500]}")
        resp.raise_for_status()
        resp_data = resp.json()
        message = resp_data["choices"][0]["message"]
        content = (message.get("content") or "").strip()
        # Fallback for reasoning models (gpt-oss, etc.)
        if not content:
            content = (message.get("reasoning_content") or message.get("reasoning") or "").strip()

        # Strip markdown code fences if present
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", content)
        raw = match.group(1) if match else content

        # Try to parse JSON
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[Extractor] JSON parse error: {e}")
            print(f"[Extractor] Raw content (len={len(raw)}): {raw[:500]!r}")
            print(f"[Extractor] Full message keys: {list(message.keys())}")
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
        print(f"[Extractor] Primary LLM error: {e}")
        
        # Fallback на Ollama якщо доступний
        if fallback_url and fallback_model:
            print(f"[Extractor] Fallback to Ollama...")
            try:
                resp = requests.post(
                    fallback_url,
                    json={
                        "model": fallback_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False
                    },
                    timeout=450,
                )
                resp.raise_for_status()
                content = resp.json()["message"]["content"].strip()

                # Strip markdown code fences if present
                match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", content)
                raw = match.group(1) if match else content

                # Try to parse JSON
                try:
                    items = json.loads(raw)
                except json.JSONDecodeError as e:
                    print(f"[Extractor] JSON parse error (fallback): {e}")
                    print(f"[Extractor] Raw content: {raw[:200]}...")
                    # Try to fix common JSON issues
                    array_match = re.search(r"\[[\s\S]*\]", raw)
                    if array_match:
                        try:
                            items = json.loads(array_match.group(0))
                        except json.JSONDecodeError:
                            print(f"[Extractor] Could not fix JSON (fallback)")
                            return []
                    else:
                        return []

                if not isinstance(items, list):
                    print(f"[Extractor] Expected list, got {type(items)} (fallback)")
                    return []
                print(f"[Extractor] Successfully extracted with Ollama fallback")
                return [
                    i for i in items
                    if isinstance(i, dict)
                    and i.get("type") in ("fact", "intent", "emotion", "behavior")
                    and isinstance(i.get("value"), str)
                    and i["value"].strip()
                ]
            except Exception as ollama_error:
                print(f"[Extractor] Ollama fallback error: {ollama_error}")
                return []
        else:
            print(f"[Extractor] No fallback available")
            return []
