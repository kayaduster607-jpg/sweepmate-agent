"""Render one shared diagram model to a crisp PNG and editable SVG."""

from html import escape
from pathlib import Path
import os

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SIZE = (1600, 1040)
BACKGROUND = "#F6F7FA"
INK = "#142237"
MUTED = "#526277"
BLUE = "#245FE8"
FONT = Path(os.environ.get("SWEEPMATE_DIAGRAM_FONT", r"C:\Windows\Fonts\msyh.ttc"))


class Canvas:
    """Keep vector and bitmap geometry in sync instead of drawing twice by hand."""

    def __init__(self):
        self.image = Image.new("RGB", SIZE, BACKGROUND)
        self.draw = ImageDraw.Draw(self.image)
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1040" viewBox="0 0 1600 1040">',
                    f'<rect width="1600" height="1040" fill="{BACKGROUND}"/>']

    def rectangle(self, box, fill, outline=None, radius=20):
        x1, y1, x2, y2 = box
        self.draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2)
        stroke = f' stroke="{outline}" stroke-width="2"' if outline else ""
        self.svg.append(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" rx="{radius}" fill="{fill}"{stroke}/>')

    def text(self, position, value, size=25, fill=INK):
        x, y = position
        font = ImageFont.truetype(str(FONT), size)
        self.draw.text(position, value, font=font, fill=fill, anchor="lt")
        self.svg.append(f'<text x="{x}" y="{y}" dominant-baseline="text-before-edge" font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif" font-size="{size}" fill="{fill}">{escape(value)}</text>')

    def line(self, points, color=BLUE, width=3, arrow=False):
        self.draw.line(points, fill=color, width=width, joint="curve")
        self.svg.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="{width}"/>')
        if arrow:
            x, y = points[-1]
            polygon = [(x, y), (x - 11, y - 6), (x - 11, y + 6)]
            self.draw.polygon(polygon, fill=color)
            self.svg.append(f'<polygon points="{" ".join(f"{a},{b}" for a,b in polygon)}" fill="{color}"/>')


def entry(canvas, box, label, title, detail):
    x, y, _, _ = box
    canvas.rectangle(box, "#FFFFFF", "#DCE2EC")
    canvas.text((x + 26, y + 24), label, 18, BLUE)
    canvas.text((x + 26, y + 62), title, 29)
    canvas.text((x + 26, y + 110), detail, 21, MUTED)


def draw_diagram():
    canvas = Canvas()
    canvas.text((72, 45), "SWEEPMATE / AGENT + KNOWLEDGE", 19, BLUE)
    canvas.text((70, 91), "SweepMate Agent", 54)
    canvas.text((73, 175), "知识检索、工具调用与使用报告，共用一个可追踪的客服流程。", 27, MUTED)
    canvas.text((72, 240), "01  CONVERSATION", 18, MUTED)
    canvas.text((526, 240), "02  LANGGRAPH", 18, MUTED)
    canvas.text((1194, 240), "03  MODEL PROVIDER", 18, MUTED)
    canvas.rectangle((70, 280, 400, 550), "#FFFFFF", "#DCE2EC")
    canvas.text((100, 312), "Streamlit 对话界面", 27)
    canvas.text((100, 373), "用户提问 / 历史消息", 23, MUTED)
    canvas.text((100, 423), "行动与工具状态", 23, MUTED)
    canvas.text((100, 473), "最终回答 / 演示报告", 23, MUTED)
    canvas.rectangle((520, 280, 1070, 550), INK)
    canvas.text((550, 311), "ReAct 状态图", 29, "#FFFFFF")
    canvas.text((550, 372), "agent : 模型决定回答或调用工具", 24, "#D5E4F9")
    canvas.text((550, 422), "tools : 执行后返回 agent", 24, "#D5E4F9")
    canvas.text((550, 478), "消息追加 / 模式标记 / 内存检查点", 23, "#92B7FF")
    canvas.rectangle((1190, 280, 1530, 550), "#FFFFFF", "#DCE2EC")
    canvas.text((1220, 312), "SiliconFlow", 28)
    canvas.text((1220, 372), "OpenAI 兼容接口", 23, MUTED)
    canvas.text((1220, 422), "Chat / Embeddings", 23, MUTED)
    canvas.text((1220, 473), "进程环境提供凭据", 23, MUTED)
    canvas.line([(400, 414), (520, 414)], arrow=True)
    canvas.line([(1070, 414), (1190, 414)], arrow=True)
    canvas.line([(650, 550), (650, 604), (420, 604), (420, 660)])
    canvas.line([(950, 550), (950, 604), (1190, 604), (1190, 660)])
    canvas.rectangle((70, 660, 770, 900), "#EAF0FC", radius=18)
    canvas.text((102, 687), "RAG / 知识工具", 28, BLUE)
    canvas.text((102, 745), "TXT / PDF  ->  分片  ->  Embedding  ->  Chroma", 23)
    canvas.text((102, 795), "Top-3 检索  ->  基于资料总结  ->  工具结果", 23)
    canvas.text((102, 848), "FAQ保留来源信息；本地索引独立构建。", 21, MUTED)
    canvas.rectangle((850, 660, 1530, 900), "#FFFFFF", "#DCE2EC", radius=18)
    canvas.text((882, 687), "REPORT / 模式与记录", 28, BLUE)
    canvas.text((882, 745), "报告工具  ->  is_report_mode  ->  切换提示词", 23)
    canvas.text((882, 795), "示例CSV  ->  查询记录  ->  生成中文报告", 23)
    canvas.text((882, 848), "120条合成记录；天气、身份、位置为模拟。", 21, MUTED)
    canvas.text((72, 964), "本机学习演示 / 不附带原知识库、历史对话、数据库或模型密钥", 24, MUTED)
    return canvas



def main():
    if not FONT.is_file():
        raise SystemExit("Set SWEEPMATE_DIAGRAM_FONT to a CJK TrueType font path.")
    canvas = draw_diagram()
    assets = ROOT / "docs/assets"
    assets.mkdir(parents=True, exist_ok=True)
    canvas.image.save(assets / "sweepmate-flow.png")
    (assets / "sweepmate-flow.svg").write_text("\n".join(canvas.svg + ["</svg>"]), encoding="utf-8")
    print("Generated architecture PNG and SVG.")


if __name__ == "__main__":
    main()
