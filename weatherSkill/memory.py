"""
用户偏好记忆管理模块
用于存储和检索用户的偏好设置
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional

MEMORY_FILE = Path(__file__).resolve().parent / "user_memory.json"


def load_memory() -> Dict[str, Any]:
    """加载用户记忆"""
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_memory(memory: Dict[str, Any]) -> None:
    """保存用户记忆"""
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def get_user_preference(key: str, default: Any = None) -> Any:
    """获取用户特定偏好"""
    memory = load_memory()
    return memory.get("preferences", {}).get(key, default)


def set_user_preference(key: str, value: Any) -> None:
    """设置用户偏好"""
    memory = load_memory()
    if "preferences" not in memory:
        memory["preferences"] = {}
    memory["preferences"][key] = value
    save_memory(memory)


def get_all_preferences() -> Dict[str, Any]:
    """获取所有用户偏好"""
    memory = load_memory()
    return memory.get("preferences", {})


def clear_preferences() -> None:
    """清除所有用户偏好"""
    memory = load_memory()
    memory["preferences"] = {}
    save_memory(memory)


def format_preferences_for_prompt() -> str:
    """将用户偏好格式化为提示词可用的字符串"""
    prefs = get_all_preferences()
    if not prefs:
        return "暂无用户偏好记录。"

    lines = ["已记录的用户偏好:"]
    for key, value in prefs.items():
        lines.append(f"  - {key}: {value}")
    return "\n".join(lines)
