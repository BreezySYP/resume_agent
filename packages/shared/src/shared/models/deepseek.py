from functools import lru_cache

from langchain_deepseek import ChatDeepSeek
import os

api_key = os.getenv("DEEP_SEEK_KEY")

@lru_cache(maxsize=1)
def get_deepseek() -> ChatDeepSeek:

    return ChatDeepSeek(
        model="deepseek-v4-flash",
        api_key=api_key
    )


if __name__ == "__main__":
    resp = get_deepseek().invoke("液冷数据中心龙头股有哪些")

    print(resp.content)