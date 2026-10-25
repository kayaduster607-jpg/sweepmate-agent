import os
import csv
import json
from utils.logger_handler import logger
from langchain_core.tools import tool
from rag.rag_service import RagSummarizeService
import random
from utils.config_handler import agent_conf
from utils.path_tool import get_abs_path

# Construct the retrieval stack only when that tool is actually used.
rag = None

user_ids = ["1001", "1002", "1003", "1004", "1005", "1006", "1007", "1008", "1009", "1010",]
month_arr = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
             "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12", ]

external_data = {}


@tool(description="从向量存储中检索参考资料")
def rag_summarize(query: str) -> str:
    global rag
    if rag is None:
        rag = RagSummarizeService()
    return rag.rag_summarize(query)


@tool(description="返回指定城市的固定演示天气，不是真实天气API")
def get_weather(city: str) -> str:
    return f"城市{city}天气为晴天，气温26摄氏度，空气湿度50%，南风1级，AQI21，最近6小时降雨概率极低"


@tool(description="随机选择一个演示城市，不读取用户真实位置")
def get_user_location() -> str:
    return random.choice(["深圳", "合肥", "杭州"])


@tool(description="随机选择一个合成用户ID，不代表当前用户身份")
def get_user_id() -> str:
    return random.choice(user_ids)


@tool(description="随机选择2025年的演示月份，并非读取当前系统月份")
def get_current_month() -> str:
    return random.choice(month_arr)


def read_external_records(path):
    """Read the documented CSV schema, including quoted commas correctly."""
    records = {}
    fields = {"user_id", "feature", "efficiency", "consumables", "comparison", "month"}
    with open(path, "r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not fields.issubset(reader.fieldnames or []):
            raise ValueError("CSV must contain: " + ", ".join(sorted(fields)))
        for row in reader:
            user_id, month = row["user_id"], row["month"]
            records.setdefault(user_id, {})[month] = {
                "特征": row["feature"], "效率": row["efficiency"],
                "耗材": row["consumables"], "对比": row["comparison"],
            }
    return records


def generate_external_data():
    """Load the configured record set once; published records are synthetic."""
    if external_data:
        return
    path = get_abs_path(agent_conf["external_data_path"])
    if not os.path.isfile(path):
        raise FileNotFoundError("Configured external CSV does not exist")
    external_data.update(read_external_records(path))



@tool(description="从外部系统中获取指定用户在指定月份的使用记录，以纯字符串形式返回， 如果未检索到返回空字符串")
def fetch_external_data(user_id: str, month: str) -> str:
    generate_external_data()

    try:
        return json.dumps(external_data[user_id][month], ensure_ascii=False)
    except KeyError:
        logger.warning(f"[fetch_external_data]未能检索到用户：{user_id}在{month}的使用记录数据")
        return ""


@tool(description="无入参，无返回值，调用后触发中间件自动为报告生成的场景动态注入上下文信息，为后续提示词切换提供上下文信息")
def fill_context_for_report():
    return "fill_context_for_report已调用"

# if __name__ == "__main__":
#     print(fetch_external_data("1001", "2025-01"))
