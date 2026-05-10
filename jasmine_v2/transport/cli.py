import argparse

from jasmine_v2.core.events import IncomingEvent
from jasmine_v2.core.runner import run_event


def main():
    parser = argparse.ArgumentParser(description="Jasmine v2 CLI transport")
    parser.add_argument("text", help="User message text")
    parser.add_argument("--chat-id", default="cli")
    parser.add_argument("--user-id", default="local_user")
    parser.add_argument("--user-name", default="Local User")

    args = parser.parse_args()

    event = IncomingEvent(
        transport="cli",
        chat_id=args.chat_id,
        user_id=args.user_id,
        user_name=args.user_name,
        text=args.text,
    )

    result = run_event(event)

    print("=== Jasmine v2 result ===")
    print(result.get("final_response", ""))

    print("\n=== Debug log ===")
    for line in result.get("debug_log", []):
        print(line)


if __name__ == "__main__":
    main()