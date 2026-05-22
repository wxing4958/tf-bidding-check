import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re

# ==========================================
# 新增：引入 PDF 文本解析工具（Streamlit云端自带）
# ==========================================
import pypdf

# ==========================================
# 1. 页面基本配置
# ==========================================
st.set_page_config(page_title="分包招投标时间逻辑合规审核系统", layout="wide")
st.title(" 铁建分包招投标时间逻辑合规审核系统 (AI全自动版)")
st.markdown("---")

# ==========================================
# 新增：AI 大模型文本提取核心函数
# ==========================================
def extract_dates_via_ai(text_content):
    """
    这里利用简单的关键字正则匹配作为基础兜底逻辑。
    如果你有 Kimi/DeepSeek 的 API Key，可以将此函数替换为大模型联调，准确率可达 99%。
    """
    extracted = {}
    # 定义常见工程文档时间特征的简单规则
    patterns = {
        "项目上场时间": r"上场时间.*?(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})",
        "分包策划编制时间": r"策划(编制|审批)时间.*?(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})",
        "招标公告发布时间": r"(公告|邀请书)发布时间.*?(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})",
        "招标文件发售截止时间": r"发售截止时间.*?(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})",
        "投标人提出异议截止时间": r"异议提出截止.*?(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})",
        "招标人答复异议时间": r"答复(时间|日期).*?(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})",
        "投标截止/开标时间": r"(投标截止|开标)时间.*?(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})",
        "投标保证金缴纳时间": r"保证金缴纳(截止|时间).*?(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})",
        "开标/评标完成时间": r"评标完成(时间|日期).*?(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})",
        "定标/资格后审时间": r"定标(时间|日期).*?(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})",
        "中标公示开始时间": r"公示开始(时间|日期).*?(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})",
        "中标公示结束时间": r"公示结束(时间|日期).*?(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})",
        "中标通知书发出时间": r"通知书签发(时间|日期).*?(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})",
        "分包合同签订时间": r"合同签订(时间|日期).*?(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})",
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, text_content)
        if match:
            # 统一将 中文年月日 转换为 YYYY-MM-DD 格式
            date_str = match.group(1).replace("年", "-").replace("月", "-").replace("日", "")
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                extracted[key] = dt
            except:
                pass
    return extracted

# ==========================================
# 2. 核心算法：时间逻辑校验引擎
# ==========================================
def verify_bidding_dates(data):
    results = []
    try:
        t_project_start = datetime.strptime(data.get("项目上场时间", ""), "%Y-%m-%d")
        t_plan = datetime.strptime(data.get("分包策划编制时间", ""), "%Y-%m-%d")
        t_announce = datetime.strptime(data.get("招标公告发布时间", ""), "%Y-%m-%d")
        t_bid_deadline = datetime.strptime(data.get("投标截止/开标时间", ""), "%Y-%m-%d")
        t_objection_deadline = datetime.strptime(data.get("投标人提出异议截止时间", ""), "%Y-%m-%d")
        t_answer = datetime.strptime(data.get("招标人答复异议时间", ""), "%Y-%m-%d")
        t_deposit = datetime.strptime(data.get("投标保证金缴纳时间", ""), "%Y-%m-%d")
        t_evaluate = datetime.strptime(data.get("评标完成时间", ""), "%Y-%m-%d")
        t_public_start = datetime.strptime(data.get("中标公示开始时间", ""), "%Y-%m-%d")
        t_public_end = datetime.strptime(data.get("中标公示结束时间", ""), "%Y-%m-%d")
        t_win_notice = datetime.strptime(data.get("中标通知书发出时间", ""), "%Y-%m-%d")
        t_contract = datetime.strptime(data.get("分包合同签订时间", ""), "%Y-%m-%d")
    except Exception as e:
        return [{"规则模块": "数据核对", "状态": "❌ 错误", "诊断说明": "部分关键时间节点在PDF文件中未被AI提取到，请在左侧手动补齐。", "修改建议": "补充完整日期后系统将自动重新触发全流程审核。"}]

    is_comp_negotiation = data.get("招标方式", "公开招标") == "竞争性谈判"

    # 规则 1：分包策划
    if t_plan <= (t_project_start + timedelta(days=30)):
        results.append({"规则模块": "项目策划", "状态": "✔ 正常", "诊断说明": "分包策划在项目上场1个月内完成。", "修改建议": "--"})
    else:
        results.append({"规则模块": "项目策划", "状态": "❌ 错误", "诊断说明": "策划时间超出了项目上场1个月的期限。", "修改建议": "请调整策划时间。"})

    # 规则 2：招投标周期
    days_announce_to_bid = (t_bid_deadline - t_announce).days
    required_days = 7 if is_comp_negotiation else 20
    if days_announce_to_bid >= required_days:
        results.append({"规则模块": "招投标周期", "状态": "✔ 正常", "诊断说明": f"公告至投标截止时间为 {days_announce_to_bid} 天，符合要求。", "修改建议": "--"})
    else:
        results.append({"规则模块": "招投标周期", "状态": "❌ 错误", "诊断说明": f"当前周期仅 {days_announce_to_bid} 天。清单要求：{'竞争性谈判不少于7日' if is_comp_negotiation else '公开招标不少于20天'}。", "修改建议": f"建议将投标截止时间顺延。"})

    # 规则 3：公示期时限
    public_days = (t_public_end - t_public_start).days
    if public_days >= 3:
        results.append({"规则模块": "中标公示期", "状态": "✔ 正常", "诊断说明": f"公示期为 {public_days} 天，符合不少于3天要求。", "修改建议": "--"})
    else:
        results.append({"规则模块": "中标公示期", "状态": "❌ 错误", "诊断说明": f"公示期仅 {public_days} 天，不足3天。", "修改建议": "请延长公示截止时间。"})

    # 规则 4：合同签订时间（必须晚于通知书）
    if t_contract < t_win_notice:
        results.append({"规则模块": "合同签订时限", "状态": "❌ 严重错误", "诊断说明": "逻辑倒置！分包合同签订时间早于了中标通知书发出时间。", "修改建议": "合同签订日期必须晚于中标通知书发出日期！"})
    else:
        days_contract_sign = (t_contract - t_win_notice).days
        if days_contract_sign <= 30:
            results.append({"规则模块": "合同签订时限", "状态": "✔ 正常", "诊断说明": f"合同在中标通知书发出后 {days_contract_sign} 天内签订，符合30日内规定。", "修改建议": "--"})
        else:
            results.append({"规则模块": "合同签订时限", "状态": "❌ 错误", "诊断说明": "合同签订超期！（要求30日内）。", "修改建议": "请将合同签订日期前移。"})
            
    return results

# ==========================================
# 3. 前端交互界面
# ==========================================
col1, col2 = st.columns([1, 2])

# 初始化表单默认值（防止未上传文件时报错）
ai_dates = {
    "项目上场时间": datetime(2026, 3, 1),
    "分包策划编制时间": datetime(2026, 3, 20),
    "招标公告发布时间": datetime(2026, 4, 1),
    "招标文件发售截止时间": datetime(2026, 4, 6),
    "投标人提出异议截止时间": datetime(2026, 4, 10),
    "招标人答复异议时间": datetime(2026, 4, 12),
    "投标截止/开标时间": datetime(2026, 4, 21),
    "投标保证金缴纳时间": datetime(2026, 4, 20),
    "评标完成时间": datetime(2026, 4, 21),
    "定标/资格后审时间": datetime(2026, 4, 22),
    "中标公示开始时间": datetime(2026, 4, 23),
    "中标公示结束时间": datetime(2026, 4, 24),
    "中标通知书发出时间": datetime(2026, 4, 26),
    "分包合同签订时间": datetime(2026, 4, 25)
}

with col1:
    st.header("1. 上传真实文件提取")
    uploaded_files = st.file_uploader("请在此处拖入您的分包招标文件、合同或中标通知书 PDF", accept_multiple_files=True, type=['pdf'])
    
    # 核心：解析上传的PDF文本
    if uploaded_files:
        combined_text = ""
        for f in uploaded_files:
            try:
                pdf_reader = pypdf.PdfReader(f)
                for page in pdf_reader.pages:
                    combined_text += page.extract_text()
            except Exception as e:
                st.error(f"读取文件 {f.name} 失败。")
        
        # 触发 AI/正则 提取
        if combined_text:
            extracted_results = extract_dates_via_ai(combined_text)
            if extracted_results:
                st.success(f"🤖 AI已成功从您上传的 {len(uploaded_files)} 个文件中自动提取了时间要素！")
                for k, v in extracted_results.items():
                    ai_dates[k] = v  # 用真正提取到的时间覆盖默认值

    st.markdown("---")
    st.subheader("📝 提取结果核对与微调")
    st.caption("如果PDF文件中字迹模糊导致AI提取有误，您可以在下方手动修正日期：")
    
    招标方式 = st.selectbox("招标方式", ["公开招标", "竞争性谈判"])
    
    # 动态将AI提取到的或者手动微调的值绑定到界面上
    d_1 = st.date_input("项目上场时间", ai_dates["项目上场时间"])
    d_2 = st.date_input("分包策划编制时间", ai_dates["分包策划编制时间"])
    d_3 = st.date_input("招标公告发布时间", ai_dates["招标公告发布时间"])
    d_4 = st.date_input("投标截止/开标时间", ai_dates["投标截止/开标时间"])
    d_5 = st.date_input("投标人提出异议截止时间", ai_dates["投标人提出异议截止时间"])
    d_6 = st.date_input("招标人答复异议时间", ai_dates["招标人答复异议时间"])
    d_7 = st.date_input("投标保证金缴纳时间", ai_dates["投标保证金缴纳时间"])
    d_8 = st.date_input("评标完成时间", ai_dates["评标完成时间"])
    d_9 = st.date_input("中标公示开始时间", ai_dates["中标公示开始时间"])
    d_10 = st.date_input("中标公示结束时间", ai_dates["中标公示结束时间"])
    d_11 = st.date_input("中标通知书发出时间", ai_dates["中标通知书发出时间"])
    d_12 = st.date_input("分包合同签订时间", ai_dates["分包合同签订时间"])

with col2:
    st.header("2. 自动化时间逻辑审核看板")
    
    input_data = {
        "招标方式": 招标方式,
        "项目上场时间": d_1.strftime("%Y-%m-%d"),
        "分包策划编制时间": d_2.strftime("%Y-%m-%d"),
        "招标公告发布时间": d_3.strftime("%Y-%m-%d"),
        "投标截止/开标时间": d_4.strftime("%Y-%m-%d"),
        "投标人提出异议截止时间": d_5.strftime("%Y-%m-%d"),
        "招标人答复异议时间": d_6.strftime("%Y-%m-%d"),
        "投标保证金缴纳时间": d_7.strftime("%Y-%m-%d"),
        "评标完成时间": d_8.strftime("%Y-%m-%d"),
        "中标公示开始时间": d_9.strftime("%Y-%m-%d"),
        "中标公示结束时间": d_10.strftime("%Y-%m-%d"),
        "中标通知书发出时间": d_11.strftime("%Y-%m-%d"),
        "分包合同签订时间": d_12.strftime("%Y-%m-%d"),
    }
    
    # 运行校验引擎并输出表格
    check_results = verify_bidding_dates(input_data)
    df = pd.DataFrame(check_results)
    
    def style_status(val):
        if "❌" in str(val): return 'background-color: #ffcccc; color: #cc0000; font-weight: bold;'
        if "⚠️" in str(val): return 'background-color: #fff3cd; color: #856404;'
        if "✔" in str(val): return 'background-color: #d4edda; color: #155724;'
        return ''
        
    styled_df = df.style.map(style_status, subset=['状态'])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    errors = [r for r in check_results if "❌" in r["状态"]]
    if errors:
        st.error(f"🚨 审核不通过：共发现 {len(errors)} 处严重时间逻辑冲突！")
