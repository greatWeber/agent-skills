import re
import os
import sys
import json
from pathlib import Path

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from client import OpenAICompatibleClient
from tools import available_tools
from config import MODEL_ID, API_KEY, BASE_URL, TAVILY_API_KEY, AGENT_SYSTEM_PROMPT
from memory import (
    format_preferences_for_prompt,
    set_user_preference,
    get_user_preference,
    get_all_preferences,
)

# --- 1. 配置LLM客户端 ---
os.environ['TAVILY_API_KEY'] = TAVILY_API_KEY

llm = OpenAICompatibleClient(
    model=MODEL_ID,
    api_key=API_KEY,
    base_url=BASE_URL
)


class RejectionTracker:
    """跟踪用户拒绝次数，实现反思机制"""
    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self.rejection_count = 0
        self.rejected_attractions = []
        self.needs_reflection = False
        self.reflection_triggered = False

    def record_rejection(self, attraction: str, reason: str = ""):
        """记录一次拒绝"""
        self.rejection_count += 1
        self.rejected_attractions.append({"attraction": attraction, "reason": reason})

        if self.rejection_count >= self.threshold and not self.reflection_triggered:
            self.needs_reflection = True

    def record_acceptance(self):
        """用户接受推荐，重置计数器"""
        self.rejection_count = 0
        self.rejected_attractions = []
        self.needs_reflection = False
        self.reflection_triggered = False

    def get_strategy_state(self) -> str:
        """获取当前策略状态描述"""
        if self.reflection_triggered:
            return f"已触发反思模式。已连续拒绝 {self.rejection_count} 个推荐。请分析原因并调整策略。"
        elif self.rejection_count > 0:
            return f"用户已连续拒绝 {self.rejection_count} 个推荐。再拒绝 {self.threshold - self.rejection_count} 次将触发反思。"
        return "推荐策略正常。"

    def mark_reflection_done(self):
        """标记反思已完成"""
        self.reflection_triggered = True
        self.needs_reflection = False


class AttractionRecommender:
    """景点推荐管理器，处理主推荐和备选方案"""
    def __init__(self):
        self.current_recommendation = None
        self.recommendation_history = []
        self.pending_check = False

    def set_recommendation(self, attraction: str):
        """设置当前推荐景点"""
        self.current_recommendation = attraction
        self.pending_check = True

    def mark_checked(self, available: bool):
        """标记门票检查完成"""
        self.pending_check = False
        if available and self.current_recommendation:
            self.recommendation_history.append(self.current_recommendation)

    def get_excluded_attractions(self) -> str:
        """获取已推荐过的景点列表（逗号分隔）"""
        return ",".join(self.recommendation_history)

    def clear(self):
        """清除当前推荐"""
        self.current_recommendation = None
        self.pending_check = False


def extract_thought_action(llm_output: str) -> tuple:
    """从LLM输出中提取 Thought 和 Action"""
    # 匹配 Thought-Action 对，Action 到行尾或下一个 Thought 前结束
    match = re.search(
        r'Thought:\s*(.*?)\s*Action:\s*(.*?)(?:\n\s*(?:Thought:|Observation:|$)|$)',
        llm_output,
        re.DOTALL
    )
    if match:
        thought = match.group(1).strip()
        action = match.group(2).strip()
        return thought, action

    # 备用：简单匹配 Thought 和 Action 行
    thought_match = re.search(r'Thought:\s*(.+?)(?:\n|$)', llm_output, re.DOTALL)
    action_match = re.search(r'Action:\s*(.+?)(?:\n|$)', llm_output, re.DOTALL)

    if thought_match and action_match:
        return thought_match.group(1).strip(), action_match.group(1).strip()

    return None, None


def parse_action(action_str: str) -> tuple:
    """解析Action字符串，返回 (tool_name, kwargs) 或 ("Finish", answer)"""
    action_str = action_str.strip()

    # 检查是否是 Finish
    finish_match = re.match(r'Finish\[(.*)\]', action_str, re.DOTALL)
    if finish_match:
        return "Finish", finish_match.group(1).strip()

    # 解析工具调用: tool_name(arg1="val1", arg2="val2")
    tool_match = re.match(r'(\w+)\s*\((.*)\)', action_str, re.DOTALL)
    if not tool_match:
        return None, None

    tool_name = tool_match.group(1)
    args_str = tool_match.group(2)

    # 解析参数
    kwargs = {}
    # 匹配 key="value" 或 key='value'
    for match in re.finditer(r'(\w+)\s*=\s*["\']([^"\']*)["\']', args_str):
        kwargs[match.group(1)] = match.group(2)

    return tool_name, kwargs


def get_system_prompt(rejection_tracker: RejectionTracker) -> str:
    """构建系统提示词，注入用户偏好和策略状态"""
    user_prefs = format_preferences_for_prompt()
    strategy_state = rejection_tracker.get_strategy_state()
    return AGENT_SYSTEM_PROMPT.format(
        user_preferences=user_prefs,
        strategy_state=strategy_state
    )


def handle_user_feedback(recommender: AttractionRecommender,
                         rejection_tracker: RejectionTracker) -> str:
    """
    模拟获取用户反馈（接受/拒绝）。
    在实际应用中，这里应该通过用户输入获取。
    返回: "accept" 或 "reject"
    """
    # 这里简化处理，实际应该询问用户
    # 返回模拟的用户反馈
    return "accept"  # 或 "reject"


def run_conversation(user_prompt: str, max_iterations: int = 10):
    """
    运行完整的对话循环，包含记忆、备选方案和反思机制。
    """
    prompt_history = [f"用户请求: {user_prompt}"]
    rejection_tracker = RejectionTracker(threshold=3)
    recommender = AttractionRecommender()

    print(f"用户输入: {user_prompt}\n" + "=" * 50)

    for i in range(max_iterations):
        print(f"\n--- 循环 {i + 1} ---")

        # 构建完整提示
        full_prompt = "\n".join(prompt_history)
        system_prompt = get_system_prompt(rejection_tracker)

        # 调用LLM
        llm_output = llm.generate(full_prompt, system_prompt=system_prompt)

        # 提取 Thought 和 Action
        thought, action = extract_thought_action(llm_output)

        if not thought or not action:
            print(f"模型输出:\n{llm_output}")
            observation = "错误: 未能正确解析 Thought-Action 格式。请确保遵循 'Thought: ... Action: ...' 格式。"
            prompt_history.append(f"Observation: {observation}")
            print(f"{observation}\n" + "=" * 50)
            continue

        print(f"Thought: {thought}")
        print(f"Action: {action}")

        # 记录到历史
        prompt_history.append(f"Thought: {thought}")
        prompt_history.append(f"Action: {action}")

        # 解析Action
        tool_name, kwargs = parse_action(action)

        if tool_name == "Finish":
            final_answer = kwargs
            print(f"\n{'=' * 50}")
            print(f"任务完成！")
            print(f"最终答案: {final_answer}")
            print(f"{'=' * 50}")

            # 尝试从最终答案中提取用户偏好
            extract_and_save_preferences(final_answer)
            return final_answer

        if not tool_name or tool_name not in available_tools:
            observation = f"错误: 未定义的工具 '{tool_name}'"
            prompt_history.append(f"Observation: {observation}")
            print(f"Observation: {observation}\n" + "=" * 50)
            continue

        # 执行工具
        try:
            observation = available_tools[tool_name](**kwargs)
        except Exception as e:
            observation = f"错误: 执行工具时出错 - {e}"

        print(f"Observation: {observation}")

        # 特殊处理：记录当前推荐景点
        if tool_name == "get_attraction":
            # 从observation中提取景点名称（简化处理）
            recommender.set_recommendation("推荐景点")

        # 特殊处理：门票信息检查
        if tool_name == "check_ticket_info":
            try:
                ticket_data = json.loads(observation)
                availability = ticket_data.get("availability", "unknown")
                price = ticket_data.get("price", "unknown")
                recommender.mark_checked(availability == "available")

                # 如果门票售罄，提示获取备选
                if availability == "sold_out":
                    observation += " 门票已售罄，请使用 get_alternative_attraction 获取备选方案。"

                # 如果价格超出用户预算（假设预算已记录在偏好中），也提示备选
                budget = get_user_preference("budget")
                if budget and price != "unknown" and price != 0 and isinstance(price, (int, float)):
                    if price > budget:
                        observation += f" 注意：该景点门票({price}元)超出您的预算({budget}元)，建议寻找备选方案。"
            except json.JSONDecodeError:
                pass

        # 记录观察结果
        observation_str = f"Observation: {observation}"
        prompt_history.append(observation_str)

        # 检查是否需要触发反思
        if rejection_tracker.needs_reflection:
            reflection_msg = (
                f"注意: 用户已连续拒绝 {rejection_tracker.rejection_count} 个推荐。"
                f"请反思推荐策略，考虑:\n"
                f"1. 是否不符合用户偏好？\n"
                f"2. 是否需要询问用户的具体需求？\n"
                f"3. 是否需要尝试完全不同的景点类型？"
            )
            prompt_history.append(reflection_msg)
            rejection_tracker.mark_reflection_done()
            print(f"系统提示: {reflection_msg}")

        print("=" * 50)

    print(f"\n达到最大迭代次数 ({max_iterations})，对话结束。")
    return "对话结束，未完成任务。"


def extract_and_save_preferences(text: str):
    """
    从文本中提取用户偏好并保存。
    这是一个简化实现，实际可以使用LLM来提取结构化偏好。
    """
    # 简单的关键词匹配来提取偏好
    preference_keywords = {
        "喜欢历史文化": "interest",
        "喜欢自然风光": "interest",
        "预算": "budget",
        "不想": "dislike",
        "偏好": "preference",
    }

    for keyword, category in preference_keywords.items():
        if keyword in text:
            # 提取关键词周围的上下文作为偏好值
            set_user_preference(category, keyword)
            print(f"[记忆] 已保存用户偏好: {category} = {keyword}")


def run_conversation_with_feedback(user_prompt: str, max_iterations: int = 15):
    """
    支持实时用户反馈的对话循环。
    """
    prompt_history = [f"用户请求: {user_prompt}"]
    rejection_tracker = RejectionTracker(threshold=3)
    recommender = AttractionRecommender()
    current_recommendation = None
    rejection_count = 0

    print(f"用户输入: {user_prompt}\n" + "=" * 50)

    for i in range(max_iterations):
        print(f"\n--- 循环 {i + 1} ---")

        # 构建完整提示
        full_prompt = "\n".join(prompt_history)
        system_prompt = get_system_prompt(rejection_tracker)

        # 调用LLM
        llm_output = llm.generate(full_prompt, system_prompt=system_prompt)

        # 提取 Thought 和 Action
        thought, action = extract_thought_action(llm_output)

        if not thought or not action:
            print(f"模型输出:\n{llm_output}")
            observation = "错误: 未能正确解析 Thought-Action 格式。请确保遵循 'Thought: ... Action: ...' 格式。"
            prompt_history.append(f"Observation: {observation}")
            print(f"{observation}\n" + "=" * 50)
            continue

        print(f"Thought: {thought}")
        print(f"Action: {action}")

        # 记录到历史
        prompt_history.append(f"Thought: {thought}")
        prompt_history.append(f"Action: {action}")

        # 解析Action
        tool_name, kwargs = parse_action(action)

        if tool_name == "Finish":
            final_answer = kwargs
            current_recommendation = final_answer
            print(f"\n{'=' * 50}")
            print(f"推荐结果:")
            print(f"{final_answer}")
            print(f"{'=' * 50}")

            # 询问用户反馈
            while True:
                feedback = input("\n您对这个推荐满意吗? (yes/no/exit): ").lower().strip()
                if feedback == "exit":
                    print("感谢使用，再见！")
                    return final_answer
                elif feedback == "yes":
                    print("很高兴您满意！")
                    extract_and_save_preferences(final_answer)
                    return final_answer
                elif feedback == "no":
                    reason = input("请告诉我们原因，以便改进推荐: ")
                    rejection_count += 1
                    rejection_tracker.record_rejection(current_recommendation, reason)

                    # 保存用户反馈到偏好
                    if "去过了" in reason or "去过" in reason:
                        set_user_preference("visited_places", reason)
                        print(f"[记忆] 已记录您去过的地方")

                    # 构建反馈消息，让LLM重新推荐
                    feedback_msg = (
                        f"用户拒绝了以上推荐。原因: {reason}。"
                        f"这是第 {rejection_count} 次拒绝。"
                    )
                    if rejection_count >= 3:
                        feedback_msg += "请反思推荐策略，尝试完全不同的景点类型或询问用户更具体的需求。"
                    else:
                        feedback_msg += "请推荐其他备选景点，避免类似的问题。"

                    prompt_history.append(f"Observation: {feedback_msg}")
                    print(f"\n正在为您重新推荐...\n{'=' * 50}")
                    break  # 跳出反馈循环，继续主循环获取新推荐
                else:
                    print("请输入 yes/no/exit")

            # 继续主循环获取新推荐
            continue

        if not tool_name or tool_name not in available_tools:
            observation = f"错误: 未定义的工具 '{tool_name}'"
            prompt_history.append(f"Observation: {observation}")
            print(f"Observation: {observation}\n" + "=" * 50)
            continue

        # 执行工具
        try:
            observation = available_tools[tool_name](**kwargs)
        except Exception as e:
            observation = f"错误: 执行工具时出错 - {e}"

        print(f"Observation: {observation}")

        # 特殊处理：记录当前推荐景点
        if tool_name == "get_attraction":
            recommender.set_recommendation("推荐景点")

        # 特殊处理：门票检查
        if tool_name == "check_ticket_availability":
            recommender.mark_checked(observation == "available")
            if observation == "sold_out":
                observation += " 请使用 get_alternative_attraction 获取备选方案。"

        # 记录观察结果
        observation_str = f"Observation: {observation}"
        prompt_history.append(observation_str)

        # 检查是否需要触发反思
        if rejection_tracker.needs_reflection:
            reflection_msg = (
                f"注意: 用户已连续拒绝 {rejection_tracker.rejection_count} 个推荐。"
                f"请反思推荐策略，考虑:\n"
                f"1. 是否不符合用户偏好？\n"
                f"2. 是否需要询问用户的具体需求？\n"
                f"3. 是否需要尝试完全不同的景点类型？"
            )
            prompt_history.append(reflection_msg)
            rejection_tracker.mark_reflection_done()
            print(f"系统提示: {reflection_msg}")

        print("=" * 50)

    print(f"\n达到最大迭代次数 ({max_iterations})，对话结束。")
    return "对话结束，未完成任务。"


def interactive_mode():
    """交互模式，允许用户实时提供反馈"""
    print("=" * 50)
    print("智能旅行助手 - 交互模式")
    print("=" * 50)

    user_input = input("\n请输入您的旅行需求: ")

    # 运行支持反馈的对话
    run_conversation_with_feedback(user_input)


# --- 主入口 ---
if __name__ == "__main__":
    # 简单示例运行
    # user_prompt = "你好，请帮我查询一下今天佛山的天气，然后根据天气推荐一个合适的旅游景点。"
    # run_conversation(user_prompt)

    # 或者使用交互模式:
    interactive_mode()
