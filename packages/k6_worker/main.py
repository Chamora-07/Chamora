import asyncio
from .consumer import start_consumer


async def main():
    print("[Worker] k6 worker starting...")
    await start_consumer()


if __name__ == "__main__":
    asyncio.run(main())