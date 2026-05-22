import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re

# ==========================================
# 1. 页面基本配置 (Streamlit 傻瓜式前端)
# ==========================================
st.set_page_config(page_title="分包招投标时间逻辑合规审核系统", layout="wide")
st.title(" 铁建分包招投标时间逻辑合规审核系统")
st.markdown("---")

# ==========================================
# 2. 核心算法：时间逻辑校验引擎
# ==========================================
def verify_bidding_dates(data):
    results = []
    
    # 转换日期格式为 datetime 对象以便计算
    try:
        t_project_start = datetime.strptime(data.get("项目上场时间", ""), "%Y-%m-%d")
        t_plan = datetime.strptime(data.get("分包策划编制时间", ""), "%Y-%m-%d")
        t_announce = datetime.strptime(data.get("招标公告发布时间", ""), "%Y-%m-%d")
        t_notice_end = datetime.strptime(data.get("招标文件发售截止时间", ""), "%Y-%m-%d")
        t_bid_deadline = datetime.strptime(data.get("投标截止/开标时间", ""), "%Y-%m-%d")
        t_objection_deadline = datetime.strptime(data.get("投标人提出异议截止时间", ""), "%Y-%m-%d")
        t_answer = datetime.strptime(data.get("招标人答复异议时间", ""), "%Y-%m-%d")
        t_deposit = datetime.strptime(data.get("投标保证金缴纳时间", ""), "%Y-%m-%d")
        t_evaluate = datetime.strptime(data.get("评标完成时间", ""), "%Y-%m-%d")
        t_confirm = datetime.strptime(data.get("定标/资格后审时间", ""), "%Y-%m-%d")
        t_public_start = datetime.strptime(data.get("中标公示开始时间", ""), "%Y-%m-%d")
        t_public_end = datetime.strptime(data.get("中标公示结束时间", ""), "%Y-%m-%d")
        t_win_notice = datetime.strptime(data.get("中标通知书发出时间", ""), "%Y-%m-%d")
        t_contract = datetime.strptime(data.get("分包合同签订时间", ""), "%Y-%m-%d")
    except Exception as e:
        return [{"规则模块": "数据初始化", "状态": "❌ 错误", "诊断说明": f"日期格式解析失败，请确保格式为 YYYY-MM-DD。错误信息: {e}", "修改建议": "检查输入数据"}]

    is_comp_negotiation = data.get("招标方式", "公开招标") == "竞争性谈判"

    # 规则 1：分包策划方案需在项目上场1个月内完成 [cite: 7]
    limit_plan = t_project_start + timedelta(days=30)
    if t_plan <= limit_plan:
        results.append({"规则模块": "项目策划", "状态": "✔ 正常", "诊断说明": "分包策划在项目上场1个月内完成 [cite: 7]。", "修改建议": "--"})
    else:
        results.append({"规则模块": "项目策划", "状态": "❌ 错误", "诊断说明": f"策划时间({data['分包策划编制时间']})超出了项目上场1个月的期限({limit_plan.strftime('%Y-%m-%d')}) [cite: 7]。", "修改建议": "请将策划方案编制时间前移或核对项目上场时间。"})

    # 规则 2：公告至投标截止时间（公开招标>=20天，竞争性谈判>=7天） [cite: 7]
    days_announce_to_bid = (t_bid_deadline - t_announce).days
    required_days = 7 if is_comp_negotiation else 20
    if days_announce_to_bid >= required_days:
        results.append({"规则模块": "招投标周期", "状态": "✔ 正常", "诊断说明": f"公告至投标截止时间为 {days_announce_to_bid} 天，符合要求 [cite: 7]。", "修改建议": "--"})
    else:
        results.append({"规则模块": "招投标周期", "状态": "❌ 错误", "诊断说明": f"当前周期仅 {days_announce_to_bid} 天。法规及清单要求：{'竞争性谈判不得少于7日' if is_comp_negotiation else '距投标截止日不少于20天'} [cite: 7]。", "修改建议": f"建议将投标截止时间顺延至 { (t_announce + timedelta(days=required_days)).strftime('%Y-%m-%d') } 或更晚。"})

    # 规则 3：异议与答疑时间逻辑 [cite: 7]
    days_bid_to_objection = (t_bid_deadline - t_objection_deadline).days
    if days_bid_to_objection >= 10:
        results.append({"规则模块": "答疑时限-异议提出", "状态": "✔ 正常", "诊断说明": "投标人提出异议在投标截止10日前，符合规定 [cite: 7]。", "修改建议": "--"})
    else:
        results.append({"规则模块": "答疑时限-异议提出", "状态": "❌ 错误", "诊断说明": f"投标人提出异议时间距离投标截止仅 {days_bid_to_objection} 日（要求至少10日） [cite: 7]。", "修改建议": "应当驳回异议或相应顺延投标截止时间。"})

    # 规则 4：收到异议后3日内作出答复 [cite: 7]
    days_answer = (t_answer - t_objection_deadline).days
    if days_answer <= 3:
        results.append({"规则模块": "答疑时限-招标人答复", "状态": "✔ 正常", "诊断说明": "招标人在收到异议后3日内作出了答复 [cite: 7]。", "修改建议": "--"})
    else:
        results.append({"规则模块": "答疑时限-招标人答复", "状态": "❌ 错误", "诊断说明": f"招标人答复耗时 {days_answer} 天，超出3日内答复的要求 [cite: 7]。", "修改建议": "请将答复函签发时间调整至收到异议后3日内。"})

    # 规则 5：投标保证金缴纳时间 [cite: 7]
    if t_deposit <= t_bid_deadline:
        results.append({"规则模块": "保证金缴纳", "状态": "✔ 正常", "诊断说明": "投标保证金在投标截止日前缴纳成功 [cite: 7]。", "修改建议": "--"})
    else:
        results.append({"规则模块": "保证金缴纳", "状态": "❌ 错误", "诊断说明": "投标保证金缴纳时间晚于投标截止时间 [cite: 7]。", "修改建议": "该单位属于无效投标，请核对凭证时间或作废其投标资格。"})

    # 规则 6：开标与评标时间（当天完成，特例1-2天） [cite: 7, 13]
    if t_evaluate == t_bid_deadline:
        results.append({"规则模块": "评标时限", "状态": "✔ 正常", "诊断说明": "开标当天完成评标 [cite: 7, 13]。", "修改建议": "--"})
    elif (t_evaluate - t_bid_deadline).days <= 2:
        results.append({"规则模块": "评标时限", "状态": "⚠️ 提示", "诊断说明": "评标在开标后1-2天内完成。请确保本项目包含‘四新’或专利技术等重难点工程 。", "修改建议": "若无技术复杂特例，建议将评标时间调整为开标当天 [cite: 7, 13]。"})
    else:
        results.append({"规则模块": "评标时限", "状态": "❌ 错误", "诊断说明": "评标完成时间超出开标当天或放宽时限 [cite: 7, 13]。", "修改建议": "请核准评标报告签署日期。"})

    # 规则 7：公示期时限（不少于3天） 
    public_days = (t_public_end - t_public_start).days
    if public_days >= 3:
        results.append({"规则模块": "中标公示期", "状态": "✔ 正常", "诊断说明": f"公示期为 {public_days} 天，符合不少于3天要求 。", "修改建议": "--"})
    else:
        results.append({"规则模块": "中标公示期", "状态": "❌ 错误", "诊断说明": f"公示期仅 {public_days} 天，不足3天 。", "修改建议": "请延长公示截止时间，确保公示满3天 。"})

    # 规则 8：中标通知书发出时间（公示期结束后1-3日内） 
    days_notice_send = (t_win_notice - t_public_end).days
    if 1 <= days_notice_send <= 3:
        results.append({"规则模块": "中标通知书发出", "状态": "✔ 正常", "诊断说明": "中标通知书在公示期结束后1-3日内发出 。", "修改建议": "--"})
    else:
        results.append({"规则模块": "中标通知书发出", "状态": "❌ 错误", "诊断说明": f"发出时间在公示期结束后的第 {days_notice_send} 天（应为1-3日内） 。", "修改建议": f"建议将中标通知书发函日期修改为：{ (t_public_end + timedelta(days=1)).strftime('%Y-%m-%d') } 至 { (t_public_end + timedelta(days=3)).strftime('%Y-%m-%d') } 之间 。"})

    # 规则 9：合同签订时间（核心校验：必须晚于通知书，且在30天内） 
    if t_contract < t_win_notice:
        results.append({"规则模块": "合同签订时限", "状态": "❌ 严重错误", "诊断说明": "逻辑倒置！分包合同签订时间早于了中标通知书发出时间 。", "修改建议": "合同签订日期必须晚于中标通知书发出日期！"})
    else:
        days_contract_sign = (t_contract - t_win_notice).days
        if days_contract_sign <= 30:
            results.append({"规则模块": "合同签订时限", "状态": "✔ 正常", "诊断说明": f"合同在中标通知书发出后 {days_contract_sign} 天内签订，符合30日内规定 。", "修改建议": "--"})
        else:
            results.append({"规则模块": "合同签订时限", "状态": "❌ 错误", "诊断说明": f"合同签订超期！在中标通知书发出后第 {days_contract_sign} 天才签订（要求30日内） 。", "修改建议": f"请将合同签订日期前移至 { (t_win_notice + timedelta(days=30)).strftime('%Y-%m-%d') } 之前 。"})
            
    return results

# ==========================================
# 3. 前端交互界面设计
# ==========================================
col1, col2 = st.columns([1, 2])

with col1:
    st.header("1. 上传资料与信息提取")
    uploaded_files = st.file_uploader("支持批量上传全套招投标PDF/Word资料", accept_multiple_files=True)
    
    st.info("💡 提示：作为小白体验版，上传文件后系统会自动模拟AI智能提取出以下时间要素。您也可以在下方手动修正提取到的时间：")
    
    # 模拟从PDF/WORD中提取出的时间，小白可以直接在界面修改测试
    招标方式 = st.selectbox("招标方式", ["公开招标", "竞争性谈判"])
    项目上场时间 = st.date_input("项目上场时间", datetime(2026, 3, 1))
    分包策划编制时间 = st.date_input("分包策划编制时间", datetime(2026, 3, 20))
    招标公告发布时间 = st.date_input("招标公告发布时间", datetime(2026, 4, 1))
    招标文件发售截止时间 = st.date_input("招标文件发售截止时间", datetime(2026, 4, 6))
    投标人提出异议截止时间 = st.date_input("投标人提出异议截止时间", datetime(2026, 4, 10))
    招标人答复异议时间 = st.date_input("招标人答复异议时间", datetime(2026, 4, 12))
    投标截止_开标时间 = st.date_input("投标截止/开标时间", datetime(2026, 4, 21))
    投标保证金缴纳时间 = st.date_input("投标保证金缴纳时间", datetime(2026, 4, 20))
    评标完成时间 = st.date_input("评标完成时间", datetime(2026, 4, 21))
    定标_资格后审时间 = st.date_input("定标/资格后审时间", datetime(2026, 4, 22))
    中标公示开始时间 = st.date_input("中标公示开始时间", datetime(2026, 4, 23))
    # 此处故意制造一个公示期不足、合同时间倒置的错误用于演示
    中标公示结束时间 = st.date_input("中标公示结束时间", datetime(2026, 4, 24)) 
    中标通知书发出时间 = st.date_input("中标通知书发出时间", datetime(2026, 4, 26))
    分包合同签订时间 = st.date_input("分包合同签订时间", datetime(2026, 4, 25)) # 故意早于通知书

with col2:
    st.header("2. 自动化时间逻辑审核看板")
    
    if uploaded_files:
        st.success(f"成功读取 {len(uploaded_files)} 个分包资料文件！已自动关联时间链条。")
    
    # 构建数据载荷
    input_data = {
        "招标方式": 招标方式,
        "项目上场时间": 项目上场时间.strftime("%Y-%m-%d"),
        "分包策划编制时间": 分包策划编制时间.strftime("%Y-%m-%d"),
        "招标公告发布时间": 招标公告发布时间.strftime("%Y-%m-%d"),
        "招标文件发售截止时间": 招标文件发售截止时间.strftime("%Y-%m-%d"),
        "投标人提出异议截止时间": 投标人提出异议截止时间.strftime("%Y-%m-%d"),
        "招标人答复异议时间": 招标人答复异议时间.strftime("%Y-%m-%d"),
        "投标截止/开标时间": 投标截止_开标时间.strftime("%Y-%m-%d"),
        "投标保证金缴纳时间": 投标保证金缴纳时间.strftime("%Y-%m-%d"),
        "评标完成时间": 评标完成时间.strftime("%Y-%m-%d"),
        "定标/资格后审时间": 定标_资格后审时间.strftime("%Y-%m-%d"),
        "中标公示开始时间": 中标公示开始时间.strftime("%Y-%m-%d"),
        "中标公示结束时间": 中标公示结束时间.strftime("%Y-%m-%d"),
        "中标通知书发出时间": 中标通知书发出时间.strftime("%Y-%m-%d"),
        "分包合同签订时间": 分包合同签订时间.strftime("%Y-%m-%d"),
    }
    
    # 运行校验引擎
    check_results = verify_bidding_dates(input_data)
    df = pd.DataFrame(check_results)
    
    # 傻瓜式高亮显示：根据状态为表格染色
    def style_status(val):
        if "❌" in str(val): return 'background-color: #ffcccc; color: #cc0000; font-weight: bold;'
        if "⚠️" in str(val): return 'background-color: #fff3cd; color: #856404;'
        if "✔" in str(val): return 'background-color: #d4edda; color: #155724;'
        return ''
        
    styled_df = df.style.applymap(style_status, subset=['状态'])
    
    # 输出可视化看板
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # 汇总输出错误报告
    errors = [r for r in check_results if "❌" in r["状态"]]
    if errors:
        st.error(f"🚨 审核不通过：共发现 {len(errors)} 处严重时间逻辑冲突！建议如下：")
        for err in errors:
            st.markdown(f"**【{err['规则模块']}】** {err['诊断说明']}")
            st.markdown(f"👉 *修改建议：{err['修改建议']}*")
    else:
        st.success("🎉 审核通过！该项目的全套分包招投标时间逻辑完全合规。")
