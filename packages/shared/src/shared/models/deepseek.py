from functools import lru_cache

from langchain_deepseek import ChatDeepSeek

@lru_cache(maxsize=1)
def get_deepseek() -> ChatDeepSeek:

    return ChatDeepSeek(
        model="deepseek-v4-flash",
        api_key="sk-3422df85f94840eca12cecefb93933ae"
    )


if __name__ == "__main__":
    resp = get_deepseek().invoke("液冷数据中心龙头股有哪些")

    print(resp.content)