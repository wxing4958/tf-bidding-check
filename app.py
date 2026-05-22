import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import requests

# ==========================================
# 1. 页面基本配置
# ==========================================
st.set_page_config(page_title="铁建分包招投标时间逻辑合规审核系统", layout="wide")
st.title(" 铁建分包招投标时间逻辑合规审核系统 (全功能智能版-稳健除错版)")
st.markdown("---")

# ==========================================
# 2. 核心：调用多模态大模型对单/多文件进行联合提取
# ==========================================
def extract_data_from_multiple_scans(files_list, api_key):
    """
    智能多文件解决方案：
    大幅拉高网络传输超时上限（解决大扫描件Timeout问题），兼容新旧Pandas渲染。
    """
    if not api_key or not files_list:
        return {}
        
    upload_url = "https://api.moonshot.cn/v1/files"
    upload_headers = {"Authorization": f"Bearer {api_key}"}
    uploaded_file_ids = []
    
    try:
        # 步骤一：批量上传文件（大幅延长timeout至300秒，防止大扫描件传输超时）
        for f in files_list:
            f.seek(0)
            file_bytes = f.read()
            
            upload_files = {
                "file": (f.name, file_bytes, "application/pdf"),
                "purpose": (None, "file-extract")
            }
            # 【核心修复】：timeout设为 300秒 保证高清大图安全送达
            upload_res = requests.post(upload_url, headers=upload_headers, files=upload_files, timeout=300)
            f_id = upload_res.json().get("id")
            if f_id:
                uploaded_file_ids.append(f_id)
        
        if not uploaded_file_ids:
            st.error("❌ 所有上传的文件云端OCR预处理均失败，请检查网络或Key。")
            return {}

        # 步骤二：多文件联合上下文语义提取
        file_tags_context = "".join([f"<file>{fid}</file>\n" for fid in uploaded_file_ids])
        
        chat_url = "https://api.moonshot.cn/v1/chat/completions"
        chat_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        prompt = """
        你是一个精通中国铁建分包招投标合规审计的顶级专家。请仔细阅读我提供给你的全套分包资料（单个或多个扫描件PDF）。
        这些文件是打印后直接扫描的，可能存在格式不一、同义词繁杂、或轻微模糊的情况。
        请你建立全局联想，综合所有文件中的内容进行交叉比对，精准找出以下关键业务要素：
        
        【一、 文本要素提取】：
        1. 中标分包商名称 —— （请在中标通知书、评标报告或分包合同中，找出最终斩获该分包项目的【分包单位/供应商全称】。若未提到，请填“未在文件中提取到”）

        【二、 12个时间节点提取】：
        1. 项目上场时间 —— （进场日、开工日期、上场日期等）
        2. 分包策划编制时间 —— （分包策划审批日、三预控方案通过日等）
        3. 招标公告发布时间 —— （公告发布日、竞谈公告时间等）
        4. 投标截止/开标时间 —— （开标时间、递交投标文件截止期等）
        5. 投标人提出异议截止时间 —— （答疑提问截止日、质疑提交时间等）
        6. 招标人答复异议时间 —— （答疑澄清发出日、对异议的回复时间等）
        7. 投标保证金缴纳时间 —— （保证金截止日、递交凭证时间等）
        8. 评标完成时间 —— （评标报告签署日、评审结束时间等）
        9. 中标公示开始时间 —— （结果公示时间、公示开始日等）
        10. 中标公示结束时间 —— （公示截止日、公示结束日期等）
        11. 中标通知书发出时间 —— （通知书签发日、发出中标通知书日期等）
        12. 分包合同签订时间 —— （合同签署日期、签约时间等）

        【严格控制规则】：
        1. 必须将辨认出的所有日期格式绝对统一转化为 "YYYY-MM-DD"（例如：2026-03-01）。
        2. 如果同一节点在不同文件里有冲突，以最新更新或最终决定的日期为准。
        3. 严格以标准的纯 JSON 格式输出，不要包含任何 Markdown 标记（如 ```json），不要包含任何多余的解释。如果时间未提到，直接在 JSON 中忽略该字段。
        """
        
        chat_data = {
            "model": "moonshot-v1-8k",
            "messages": [
                {
                    "role": "system",
                    "content": f"你是专门处理工程多扫描件联合审计的OCR助手。以下是所有上传文件的云端OCR内容：\n\n{file_tags_context}"
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0
        }
        
        chat_res = requests.post(chat_url, headers=chat_headers, json=chat_data, timeout=300)
        ai_reply = chat_res.json()['choices'][0]['message']['content'].strip()
        
        if ai_reply.startswith("```json"):
            ai_reply = ai_reply.split("```json")[1].split("```")[0].strip()
        elif ai_reply.startswith("```"):
            ai_reply = ai_reply.split("```")[1].split("```")[0].strip()
            
        for fid in uploaded_file_ids:
            requests.delete(f"[https://api.moonshot.cn/v1/files/](https://api.moonshot.cn/v1/files/){fid}", headers=upload_headers)
        
        return json.loads(ai_reply)
    except Exception as e:
        st.error(f"云端数据联合提取失败。错误详情: {e}")
        return {}

# ==========================================
# 3. 时间逻辑校验引擎
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
        return [{"规则模块": "数据核对", "状态": "❌ 错误", "诊断说明": "部分关键时间节点在扫描件中未被AI自动识别到，请在左侧手动补齐/修正。", "修改建议": "人工在左侧补充完整日期后，系统将自动触发全流程硬性合规审核。"}]

    is_comp_negotiation = data.get("招标方式", "公开招标") == "竞争性谈判"

    if t_plan <= (t_project_start + timedelta(days=30)):
        results.append({"规则模块": "项目策划", "状态": "✔ 正常", "诊断说明": "分包策划在项目上场1个月内完成。", "修改建议": "--"})
    else:
        results.append({"规则模块": "项目策划", "状态": "❌ 错误", "诊断说明": "分包策划编制时间超出了项目上场1个月的期限要求。", "修改建议": "请调整分包策划方案时间。"})

    days_announce_to_bid = (t_bid_deadline - t_announce).days
    required_days = 7 if is_comp_negotiation else 20
    if days_announce_to_bid >= required_days:
        results.append({"规则模块": "招投标周期", "状态": "✔ 正常", "诊断说明": f"公告至投标截止时间为 {days_announce_to_bid} 天，符合要求。", "修改建议": "--"})
    else:
        results.append({"规则模块": "招投标周期", "状态": "❌ 错误", "诊断说明": f"当前周期仅 {days_announce_to_bid} 天。清单及法规要求：{'竞争性谈判不少于7日' if is_comp_negotiation else '公开招标不少于20天'}。", "修改建议": "建议将投标截止时间顺延以满足法定周期要求。"})

    public_days = (t_public_end - t_public_start).days
    if public_days >= 3:
        results.append({"规则模块": "中标公示期", "状态": "✔ 正常", "诊断说明": f"公示期为 {public_days} 天，符合不少于3天要求。", "修改建议": "--"})
    else:
        results.append({"规则模块": "中标公示期", "状态": "❌ 错误", "诊断说明": f"公示期仅 {public_days} 天，时限不足3天。", "修改建议": "请顺延公示截止时间。"})

    if t_contract < t_win_notice:
        results.append({"规则模块": "合同签订时限", "状态": "❌ 严重错误", "诊断说明": "核心逻辑倒置！分包合同签订时间早于了中标通知书发出时间。", "修改建议": "分包合同签订日期必须晚于中标通知书发出日期！"})
    else:
        days_contract_sign = (t_contract - t_win_notice).days
        if days_contract_sign <= 30:
            results.append({"规则模块": "合同签订时限", "状态": "✔ 正常", "诊断说明": f"合同在中标通知书发出后 {days_contract_sign} 天内签订，符合30日内规定。", "修改建议": "--"})
        else:
            results.append({"规则模块": "合同签订时限", "状态": "❌ 错误", "诊断说明": f"合同签订超期！在中标通知书发出后第 {days_contract_sign} 天才签订（要求30日内）。", "修改建议": "请将合同签署日期前移至法定30天限期内。"})
            
    return results

# ==========================================
# 4. 前端交互界面设计
# ==========================================
col1, col2 = st.columns([1, 2])

if 'ai_dates' not in st.session_state:
    st.session_state.ai_dates = {
        "项目上场时间": datetime(2026, 3, 1), "分包策划编制时间": datetime(2026, 3, 20),
        "招标公告发布时间": datetime(2026, 4, 1), "投标截止/开标时间": datetime(2026, 4, 21),
        "投标人提出异议截止时间": datetime(2026, 4, 10), "招标人答复异议时间": datetime(2026, 4, 12),
        "投标保证金缴纳时间": datetime(2026, 4, 20), "评标完成时间": datetime(2026, 4, 21),
        "中标公示开始时间": datetime(2026, 4, 23), "中标公示结束时间": datetime(2026, 4, 24),
        "中标通知书发出时间": datetime(2026, 4, 26), "分包合同签订时间": datetime(2026, 4, 25)
    }
if 'subcontractor_name' not in st.session_state:
    st.session_state.subcontractor_name = "中铁建某某分包工程有限公司 (默认预填值)"

with col1:
    st.header("1. 资料上传与高级云端OCR")
    api_key = st.text_input("🔑 请输入您的 Kimi API Key：", type="password")
    uploaded_files = st.file_uploader("支持单文件或多文件批量拖入", accept_multiple_files=True, type=['pdf'])
    
    if uploaded_files and api_key:
        with st.spinner(f"🔍 正在智能OCR识别 {len(uploaded_files)} 个文件并抓取中标单位名称..."):
            extracted_results = extract_data_from_multiple_scans(uploaded_files, api_key)
            
            if "中标分包商名称" in extracted_results:
                st.session_state.subcontractor_name = extracted_results["中标分包商名称"]
                
            for k, v in extracted_results.items():
                if k in st.session_state.ai_dates:
                    try:
                        st.session_state.ai_dates[k] = datetime.strptime(v, "%Y-%m-%d")
                    except:
                        pass
            st.success("🎉 全套文件要素提取完毕！数据已自动填充。")

    st.markdown("---")
    st.subheader("📝 提取结果核对与微调")
    
    v_sub_name = st.text_input("🏢 中标分包商名称", st.session_state.subcontractor_name)
    招标方式 = st.selectbox("招标方式", ["公开招标", "竞争性谈判"])
    
    d_1 = st.date_input("项目上场时间", st.session_state.ai_dates["项目上场时间"])
    d_2 = st.date_input("分包策划编制时间", st.session_state.ai_dates["分包策划编制时间"])
    d_3 = st.date_input("招标公告发布时间", st.session_state.ai_dates["招标公告发布时间"])
    d_4 = st.date_input("投标截止/开标时间", st.session_state.ai_dates["投标截止/开标时间"])
    d_5 = st.date_input("投标人提出异议截止时间", st.session_state.ai_dates["投标人提出异议截止时间"])
    d_6 = st.date_input("招标人答复异议时间", st.session_state.ai_dates["招标人答复异议时间"])
    d_7 = st.date_input("投标保证金缴纳时间", st.session_state.ai_dates["投标保证金缴纳时间"])
    d_8 = st.date_input("评标完成时间", st.session_state.ai_dates["评标完成时间"])
    d_9 = st.date_input("中标公示开始时间", st.session_state.ai_dates["中标公示开始时间"])
    d_10 = st.date_input("中标公示结束时间", st.session_state.ai_dates["中标公示结束时间"])
    d_11 = st.date_input("中标通知书发出时间", st.session_state.ai_dates["中标通知书发出时间"])
    d_12 = st.date_input("分包合同签订时间", st.session_state.ai_dates["分包合同签订时间"])

with col2:
    st.header("2. 自动化时间逻辑审核看板")
    st.info(f"📋 **当前审核对象（分包单位）：** {v_sub_name}")
    
    input_data = {
        "招标方式": 招标方式,
        "项目上场时间": d_1.strftime("%Y-%m-%d"), "分包策划编制时间": d_2.strftime("%Y-%m-%d"),
        "招标公告发布时间": d_3.strftime("%Y-%m-%d"), "投标截止/开标时间": d_4.strftime("%Y-%m-%d"),
        "投标人提出异议截止时间": d_5.strftime("%Y-%m-%d"), "招标人答复异议时间": d_6.strftime("%Y-%m-%d"),
        "投标保证金缴纳时间": d_7.strftime("%Y-%m-%d"), "评标完成时间": d_8.strftime("%Y-%m-%d"),
        "中标公示开始时间": d_9.strftime("%Y-%m-%d"), "中标公示结束时间": d_10.strftime("%Y-%m-%d"),
        "中标通知书发出时间": d_11.strftime("%Y-%m-%d"), "分包合同签订时间": d_12.strftime("%Y-%m-%d"),
    }
    
    check_results = verify_bidding_dates(input_data)
    df = pd.DataFrame(check_results)
    
    def style_status(val):
        if "❌" in str(val): return 'background-color: #ffcccc; color: #cc0000; font-weight: bold;'
        if "⚠️" in str(val): return 'background-color: #fff3cd; color: #856404;'
        if "✔" in str(val): return 'background-color: #d4edda; color: #155724;'
        return ''
        
    # 【核心修复】：由于新版Pandas移除了applymap，此处改为使用 .map() 确保旧版与最新版全兼容
    if hasattr(df.style, 'map'):
        styled_df = df.style.map(style_status, subset=['状态'])
    else:
        styled_df = df.style.applymap(style_status, subset=['状态'])
        
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    errors = [r for r in check_results if "❌" in r["状态"]]
    if errors:
        st.error(f"🚨 审核不通过：共发现 {len(errors)} 处严重时间逻辑冲突！")
