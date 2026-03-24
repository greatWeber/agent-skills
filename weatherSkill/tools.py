import requests
import os
from tavily import TavilyClient

def get_weather(city: str) -> str:
    """
    通过调用 wttr.in API 查询真实的天气信息。
    """
    # API端点，我们请求JSON格式的数据
    url = f"https://wttr.in/{city}?format=j1"
    
    try:
        # 发起网络请求
        response = requests.get(url)
        # 检查响应状态码是否为200 (成功)
        response.raise_for_status() 
        # 解析返回的JSON数据
        data = response.json()
        
        # 提取当前天气状况
        current_condition = data['current_condition'][0]
        weather_desc = current_condition['weatherDesc'][0]['value']
        temp_c = current_condition['temp_C']
        
        # 格式化成自然语言返回
        return f"{city}当前天气:{weather_desc}，气温{temp_c}摄氏度"
        
    except requests.exceptions.RequestException as e:
        # 处理网络错误
        return f"错误:查询天气时遇到网络问题 - {e}"
    except (KeyError, IndexError) as e:
        # 处理数据解析错误
        return f"错误:解析天气数据失败，可能是城市名称无效 - {e}"


def get_attraction(city: str, weather: str) -> str:
    """
    根据城市和天气，使用Tavily Search API搜索并返回优化后的景点推荐。
    """
    # 1. 从环境变量中读取API密钥
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return "错误:未配置TAVILY_API_KEY环境变量。"

    # 2. 初始化Tavily客户端
    tavily = TavilyClient(api_key=api_key)
    
    # 3. 构造一个精确的查询
    query = f"'{city}' 在'{weather}'天气下最值得去的旅游景点推荐及理由"
    
    try:
        # 4. 调用API，include_answer=True会返回一个综合性的回答
        response = tavily.search(query=query, search_depth="basic", include_answer=True)
        
        # 5. Tavily返回的结果已经非常干净，可以直接使用
        # response['answer'] 是一个基于所有搜索结果的总结性回答
        if response.get("answer"):
            return response["answer"]
        
        # 如果没有综合性回答，则格式化原始结果
        formatted_results = []
        for result in response.get("results", []):
            formatted_results.append(f"- {result['title']}: {result['content']}")
        
        if not formatted_results:
             return "抱歉，没有找到相关的旅游景点推荐。"

        return "根据搜索，为您找到以下信息:\n" + "\n".join(formatted_results)

    except Exception as e:
        return f"错误:执行Tavily搜索时出现问题 - {e}"


def check_ticket_info(attraction: str, city: str = "") -> str:
    """
    查询景点的门票信息，包括价格和可用性。
    返回 JSON 格式的字符串，包含 price(价格), availability(可用性), currency(货币单位)
    """
    import random
    import json

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return json.dumps({"error": "未配置TAVILY_API_KEY环境变量"})

    tavily = TavilyClient(api_key=api_key)

    # 搜索门票价格和可用性
    query = f"{city}{attraction}门票价格 多少钱 开放时间"

    try:
        response = tavily.search(query=query, search_depth="basic", include_answer=True)

        # 模拟解析搜索结果提取价格信息
        # 实际场景中可以使用更复杂的NLP来提取
        price_keywords = ["免费", "元", "门票", "价格", "成人票", "学生票"]
        search_content = response.get("answer", "")

        # 模拟价格数据（实际应该从搜索结果中解析）
        # 随机生成价格或标记为免费景点
        is_free = "免费" in search_content or "免门票" in search_content

        if is_free:
            price = 0
        else:
            # 模拟价格范围 20-150 元
            price = random.choice([20, 30, 50, 55, 70, 80, 100, 120, 150])

        # 模拟可用性
        availability = "available" if random.random() > 0.2 else "sold_out"

        result = {
            "attraction": attraction,
            "city": city,
            "price": price,
            "currency": "CNY",
            "availability": availability,
            "is_free": is_free,
            "notes": "价格仅供参考，请以官方渠道为准" if not is_free else "该景点免费开放"
        }

        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        # 如果搜索失败，返回模拟数据
        result = {
            "attraction": attraction,
            "city": city,
            "price": "unknown",
            "availability": "available",
            "error": f"查询失败: {str(e)}"
        }
        return json.dumps(result, ensure_ascii=False)


def get_alternative_attraction(city: str, weather: str, excluded: str = "") -> str:
    """
    获取备选景点推荐，排除已推荐的景点。
    excluded: 已推荐过的景点名称，用逗号分隔
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return "错误:未配置TAVILY_API_KEY环境变量。"

    tavily = TavilyClient(api_key=api_key)

    # 构造查询，排除已推荐的景点
    excluded_list = [e.strip() for e in excluded.split(",") if e.strip()]
    exclude_str = "，排除以下景点:" + "、".join(excluded_list) if excluded_list else ""

    query = f"'{city}' 在'{weather}'天气下最值得去的旅游景点推荐{exclude_str}，要求是不同的备选方案"

    try:
        response = tavily.search(query=query, search_depth="basic", include_answer=True)

        if response.get("answer"):
            return response["answer"]

        formatted_results = []
        for result in response.get("results", []):
            formatted_results.append(f"- {result['title']}: {result['content']}")

        if not formatted_results:
            return "抱歉，没有找到其他备选景点。"

        return "为您找到以下备选景点:\n" + "\n".join(formatted_results)

    except Exception as e:
        return f"错误:执行Tavily搜索时出现问题 - {e}"


# 将所有工具函数放入一个字典，方便后续调用
available_tools = {
    "get_weather": get_weather,
    "get_attraction": get_attraction,
    "check_ticket_info": check_ticket_info,
    "get_alternative_attraction": get_alternative_attraction,
}
