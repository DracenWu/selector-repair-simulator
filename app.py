from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
from io import StringIO

import pandas as pd
import streamlit as st
from parsel import Selector


try:
    import scrapling  # noqa: F401

    SCRAPLING_AVAILABLE = True
except Exception:
    SCRAPLING_AVAILABLE = False


@dataclass(frozen=True)
class PageVariant:
    name: str
    html: str
    note: str
    change_ticket: str


BASE_HTML = """
<html><body><main class="job-list">
  <article class="job-card" data-id="p001">
    <h2 class="title"><a href="/jobs/1">Python 爬虫工程师</a></h2>
    <span class="company">星海数据</span><span class="city">南京</span><span class="salary">15-25K</span>
  </article>
  <article class="job-card" data-id="p002">
    <h2 class="title"><a href="/jobs/2">数据采集开发实习生</a></h2>
    <span class="company">云舟科技</span><span class="city">苏州</span><span class="salary">180-220/天</span>
  </article>
</main></body></html>
"""

CLASS_CHANGED_HTML = """
<html><body><main class="job-list">
  <article class="position-card" data-id="p001">
    <h2 class="job-title-2026"><a href="/jobs/1">Python 爬虫工程师</a></h2>
    <span class="org-name">星海数据</span><span class="work-city">南京</span><span class="pay-range">15-25K</span>
  </article>
  <article class="position-card" data-id="p002">
    <h2 class="job-title-2026"><a href="/jobs/2">数据采集开发实习生</a></h2>
    <span class="org-name">云舟科技</span><span class="work-city">苏州</span><span class="pay-range">180-220/天</span>
  </article>
</main></body></html>
"""

LAYOUT_CHANGED_HTML = """
<html><body><section id="positions">
  <div class="ad">限时课程广告</div>
  <div class="row" data-id="p001">
    <header><a class="name" href="/jobs/1">Python 爬虫工程师</a></header>
    <p><b>星海数据</b> · <i>南京</i> · <em>15-25K</em></p>
  </div>
  <div class="row" data-id="p002">
    <header><a class="name" href="/jobs/2">数据采集开发实习生</a></header>
    <p><b>云舟科技</b> · <i>苏州</i> · <em>180-220/天</em></p>
  </div>
</section></body></html>
"""

VARIANTS = [
    PageVariant("基准版本", BASE_HTML, "结构稳定，基准规则应完整命中。", "CHG-000 基准版本"),
    PageVariant("类名变更", CLASS_CHANGED_HTML, "前端改版后字段语义不变、类名整体替换。", "CHG-101 CSS 命名规范升级"),
    PageVariant("布局变更", LAYOUT_CHANGED_HTML, "卡片层级重组并插入非业务节点。", "CHG-102 列表组件重构"),
]

TARGET_TEXTS = {
    "职位标题": ["Python 爬虫工程师", "数据采集开发实习生"],
    "公司名称": ["星海数据", "云舟科技"],
    "城市": ["南京", "苏州"],
    "薪资": ["15-25K", "180-220/天"],
}

FALLBACK_SELECTORS = {
    "职位标题": ["h2 a::text", ".job-title-2026 a::text", "header a::text", "a.name::text"],
    "公司名称": [".company::text", ".org-name::text", "p b::text"],
    "城市": [".city::text", ".work-city::text", "p i::text"],
    "薪资": [".salary::text", ".pay-range::text", "p em::text"],
}


def extract_with_css(html: str, css: str) -> list[str]:
    selector = Selector(text=html)
    return [item.strip() for item in selector.css(css).getall() if item.strip()]


def adaptive_extract(html: str, field: str, failed_selector: str) -> tuple[list[str], str]:
    for candidate in FALLBACK_SELECTORS[field]:
        values = extract_with_css(html, candidate)
        if values:
            return values, candidate

    text = " ".join(Selector(text=html).css("body ::text").getall())
    matches = []
    for expected in TARGET_TEXTS[field]:
        match = get_close_matches(expected, text.split(), n=1, cutoff=0.55)
        if match:
            matches.append(match[0])
    return matches, f"文本近似匹配：{failed_selector}"


def hit_rate(values: list[str], field: str) -> float:
    expected = TARGET_TEXTS[field]
    hit_count = sum(1 for item in expected if item in values)
    return round(hit_count / len(expected), 2)


def build_report(task_id: str, role: str, field: str, rows: list[dict[str, object]]) -> str:
    frame = pd.DataFrame(rows)
    output = StringIO()
    output.write(f"# 采集规则稳定性验证报告 {task_id}\n\n")
    output.write(f"- 岗位角色：{role}\n- 验证字段：{field}\n")
    output.write(f"- 总体通过率：{frame['验收结果'].eq('通过').mean():.0%}\n\n")
    output.write("## 验证明细\n\n")
    output.write(frame.to_markdown(index=False))
    output.write("\n\n## 边界说明\n\n本仿真只使用本地可控页面，不连接外部网站。生产迁移须取得数据源授权并执行变更评审。\n")
    return output.getvalue()


st.set_page_config(page_title="采集规则稳定性验证与修复仿真", layout="wide")
st.title("网页采集规则稳定性验证与修复仿真")
st.caption("生产任务映射：数据采集开发人员接收页面改版工单，验证字段规则、完成修复并提交回归报告。")

with st.expander("生产任务单与验收标准", expanded=True):
    st.markdown(
        """
        **任务背景：** 企业数据采集任务上线后，目标页面发生版本变更，需要在不遗漏、不串字段的前提下恢复采集规则。  
        **工作流程：** 读取变更工单 → 建立基准结果 → 执行多版本回归 → 定位失效原因 → 修复规则 → 输出验证报告。  
        **交付物：** 规则清单、变更影响分析、回归测试记录、稳定性验证报告。  
        **验收标准：** 每个页面变体字段命中率达到100%，修复过程可解释，禁止连接未授权网站。
        """
    )

with st.sidebar:
    task_id = st.text_input("任务编号", value="SIM-SEL-001")
    role = st.selectbox("岗位角色", ["数据采集开发工程师", "数据质量测试工程师", "数据产品实施工程师"])
    field = st.selectbox("待验证字段", list(TARGET_TEXTS))
    css = st.text_input("基准 CSS 选择器", value=FALLBACK_SELECTORS[field][0])
    use_adaptive = st.checkbox("启用可解释的候选规则修复", value=True)
    pass_line = st.slider("验收阈值", 0.5, 1.0, 1.0, 0.1)
    st.caption(f"Scrapling 环境状态：{'已安装' if SCRAPLING_AVAILABLE else '未安装'}；当前仿真不直接调用外部网站。")

cols = st.columns(3)
rows: list[dict[str, object]] = []
for col, variant in zip(cols, VARIANTS):
    with col:
        st.subheader(variant.name)
        st.caption(f"{variant.change_ticket}｜{variant.note}")
        original_values = extract_with_css(variant.html, css)
        initial_score = hit_rate(original_values, field)
        final_values = original_values
        repaired_by = "无需修复" if initial_score >= pass_line else "未修复"
        if initial_score < pass_line and use_adaptive:
            candidate_values, candidate = adaptive_extract(variant.html, field, css)
            if candidate_values:
                final_values = candidate_values
                repaired_by = candidate
        final_score = hit_rate(final_values, field)
        accepted = final_score >= pass_line
        st.metric("修复后命中率", f"{final_score:.0%}", delta=f"{final_score - initial_score:+.0%}")
        st.write("；".join(final_values) if final_values else "未提取到结果")
        st.success("验收通过") if accepted else st.error("验收未通过")
        if repaired_by not in {"无需修复", "未修复"}:
            st.info(f"候选修复规则：{repaired_by}")
        with st.expander("查看测试页面与基准值"):
            st.code(variant.html, language="html")
            st.write({"期望值": TARGET_TEXTS[field], "初始结果": original_values})
        rows.append(
            {
                "变更工单": variant.change_ticket,
                "页面版本": variant.name,
                "字段": field,
                "基准规则": css,
                "初始命中率": initial_score,
                "修复方式": repaired_by,
                "最终命中率": final_score,
                "验收结果": "通过" if accepted else "不通过",
            }
        )

result_df = pd.DataFrame(rows)
st.divider()
st.subheader("回归验证与交付")
m1, m2, m3 = st.columns(3)
m1.metric("页面版本", len(result_df))
m2.metric("平均最终命中率", f"{result_df['最终命中率'].mean():.0%}")
m3.metric("验收通过率", f"{result_df['验收结果'].eq('通过').mean():.0%}")
st.dataframe(result_df, width="stretch")

report = build_report(task_id, role, field, rows)
download_col1, download_col2 = st.columns(2)
download_col1.download_button(
    "下载回归记录 CSV", result_df.to_csv(index=False).encode("utf-8-sig"), f"{task_id}_回归记录.csv", "text/csv"
)
download_col2.download_button("下载稳定性报告 Markdown", report, f"{task_id}_稳定性报告.md", "text/markdown")

st.info(
    "教学边界：候选规则修复用于解释稳定性验证流程，不代表自动绕过网站限制。"
    "迁移到真实业务时，应由企业提供授权测试页面、字段标准和变更工单。"
)
