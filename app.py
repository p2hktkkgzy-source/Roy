import streamlit as st
import pandas as pd
from openai import OpenAI
import json
import time
import plotly.express as px
from collections import Counter

st.set_page_config(page_title="BeautyLens AI - 消费者洞察平台", layout="wide")

st.title("💄 BeautyLens AI")
st.caption("AI驱动的消费者洞察与科学证据平台")
st.divider()

# ========== 侧边栏设置 ==========
with st.sidebar:
    st.header("⚙️ 设置")
    
    api_key = st.text_input(
        "DeepSeek API Key", 
        type="password",
        help="在 platform.deepseek.com 获取"
    )
    
    analysis_limit = st.slider(
        "📊 分析评论条数",
        min_value=10,
        max_value=200,
        value=100,
        step=10,
        help="建议首次分析先选20条测试，确认效果后再拉满"
    )
    
    st.caption("🔒 API Key仅用于本次分析，不会存储")
    
    if api_key:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# ========== 主界面 ==========
uploaded_file = st.file_uploader("📂 上传评论数据（CSV格式）", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.success(f"✅ 成功加载 {len(df)} 条评论")
    
    # 智能识别评论列
    comment_col = None
    for col in df.columns:
        if col in ["comment", "评论", "content", "内容", "评价"]:
            comment_col = col
            break
    
    if comment_col is None:
        st.error(f"❌ 找不到评论列，当前列名：{list(df.columns)}")
        st.stop()
    
    st.info(f"📋 检测到评论列：『{comment_col}』，共 {len(df)} 条")
    
    with st.expander("📋 点击预览原始数据"):
        st.dataframe(df.head(10))
    
    st.divider()
    
    # ========== 分析按钮 ==========
    if st.button("🚀 开始AI分析", type="primary"):
        
        if not api_key:
            st.error("❌ 请先在左侧输入 DeepSeek API Key")
            st.stop()
        
        all_comments = df[comment_col].dropna().tolist()
        sample = all_comments[:analysis_limit]
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        
        # ===== 优化后的Prompt =====
        system_prompt = """你是护肤品消费者洞察专家，擅长从用户评论中提取关键信息。

请严格区分以下概念：
1. **user_skin_type**：用户描述的自身肤质，如"我是敏感肌""我是干皮""我是油皮""换季容易过敏"
   没有明确提及则填"未知"
2. **pain_points**：用户对产品的负面反馈（产品本身的问题），如"太油了""闷痘""刺痛""厚重""难推开"
   不包括用户自身肤质描述
3. **positive_points**：用户对产品的正面反馈，如"修护很好""保湿不错""退红明显""吸收快"
4. **emotion**：整体情绪占比，positive和negative总和为100

输出JSON格式：
{
  "user_skin_type": "敏感肌/干皮/油皮/混油/中性/未知",
  "pain_points": ["负面反馈1", "负面反馈2"],
  "positive_points": ["正面反馈1", "正面反馈2"],
  "emotion": {"positive": 0, "negative": 0}
}

只返回JSON，不要其他文字。"""
        
        # ===== 逐条分析 =====
        for i, comment in enumerate(sample):
            status_text.text(f"🔄 正在分析第 {i+1}/{len(sample)} 条评论...")
            
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"评论：{comment}"}
                    ],
                    temperature=0.3,
                    max_tokens=300
                )
                
                result_text = response.choices[0].message.content
                result_text = result_text.replace("```json", "").replace("```", "").strip()
                data = json.loads(result_text)
                data["original"] = comment
                results.append(data)
                
            except Exception as e:
                results.append({
                    "original": comment,
                    "user_skin_type": "未知",
                    "pain_points": [],
                    "positive_points": [],
                    "emotion": {"positive": 50, "negative": 50},
                    "error": str(e)[:50]
                })
            
            progress_bar.progress((i + 1) / len(sample))
            time.sleep(0.05)
        
        status_text.text("✅ 分析完成！")
        st.session_state["results"] = results
        st.balloons()

# ========== 结果展示 ==========
if "results" in st.session_state:
    results = st.session_state["results"]
    valid_results = [r for r in results if "error" not in r]
    
    if not valid_results:
        st.warning("⚠️ 没有有效的分析结果，请检查API配置")
        st.stop()
    
    st.divider()
    st.subheader("📊 可视化仪表盘")
    
    # ===== 第一行：KPI卡片 =====
    col1, col2, col3, col4 = st.columns(4)
    
    total = len(valid_results)
    pos_avg = sum([r.get("emotion", {}).get("positive", 50) for r in valid_results]) / total
    neg_avg = sum([r.get("emotion", {}).get("negative", 50) for r in valid_results]) / total
    
    skin_types = [r.get("user_skin_type", "未知") for r in valid_results]
    skin_counts = Counter(skin_types)
    top_skin = skin_counts.most_common(1)[0][0] if skin_counts else "无"
    top_skin_count = skin_counts.most_common(1)[0][1] if skin_counts else 0
    
    all_pain = []
    for r in valid_results:
        all_pain.extend(r.get("pain_points", []))
    pain_counts = Counter(all_pain)
    top_pain = pain_counts.most_common(1)[0][0] if pain_counts else "无"
    top_pain_count = pain_counts.most_common(1)[0][1] if pain_counts else 0
    
    col1.metric("📝 分析评论数", f"{total} 条")
    col2.metric("😊 平均正面情绪", f"{pos_avg:.0f}%")
    col3.metric("🧴 最多肤质", f"{top_skin} ({top_skin_count}人)")
    col4.metric("🔴 最多痛点", f"「{top_pain}」({top_pain_count}次)")
    
    st.divider()
    
    # ===== 第二行：痛点 + 肤质 =====
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔴 消费者痛点 TOP 10")
        if pain_counts:
            pain_df = pd.DataFrame(pain_counts.most_common(10), columns=["痛点", "提及次数"])
            fig = px.bar(pain_df, x="提及次数", y="痛点", orientation='h',
                         color="提及次数", color_continuous_scale="Reds",
                         title="产品负面反馈分布")
            fig.update_layout(height=400, showlegend=False, xaxis_title="提及次数", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("✅ 暂无痛点数据，产品表现很好！")
    
    with col2:
        st.subheader("🧴 用户肤质分布")
        filtered_skin = {k: v for k, v in skin_counts.items() if k != "未知"}
        if filtered_skin:
            skin_df = pd.DataFrame(filtered_skin.items(), columns=["肤质", "人数"])
            fig = px.pie(skin_df, values="人数", names="肤质",
                         title="目标用户画像",
                         color_discrete_sequence=px.colors.qualitative.Set3)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无明确的肤质信息")
    
    # ===== 第三行：情绪 + 正面反馈 =====
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("😊 整体情绪分布")
        emotion_df = pd.DataFrame({
            "情绪": ["正面", "负面"],
            "占比": [pos_avg, neg_avg]
        })
        fig = px.pie(emotion_df, values="占比", names="情绪",
                     title=f"正面 {pos_avg:.0f}% / 负面 {neg_avg:.0f}%",
                     color="情绪",
                     color_discrete_map={"正面": "#4CAF50", "负面": "#F44336"})
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col4:
        st.subheader("🟢 消费者点赞 TOP 10")
        all_positive = []
        for r in valid_results:
            all_positive.extend(r.get("positive_points", []))
        pos_counts = Counter(all_positive)
        if pos_counts:
            pos_df = pd.DataFrame(pos_counts.most_common(10), columns=["优点", "提及次数"])
            fig = px.bar(pos_df, x="提及次数", y="优点", orientation='h',
                         color="提及次数", color_continuous_scale="Greens",
                         title="产品正面反馈分布")
            fig.update_layout(height=400, showlegend=False, xaxis_title="提及次数", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无正面反馈数据")
    
    st.divider()
    
    # ===== 详细数据表格 =====
    with st.expander("📋 查看每条评论的详细分析结果"):
        display_df = pd.DataFrame(valid_results)
        cols = ["original", "user_skin_type", "pain_points", "positive_points", "emotion"]
        available_cols = [c for c in cols if c in display_df.columns]
        st.dataframe(display_df[available_cols], use_container_width=True)
    
    # ===== 下载按钮 =====
    csv_data = pd.DataFrame(valid_results).to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 下载完整分析结果 (CSV)",
        data=csv_data,
        file_name=f"beautylens_analysis_{len(valid_results)}条.csv",
        mime="text/csv"
    )
    
    st.caption(f"✅ 共分析 {len(valid_results)} 条评论 | 失败 {len(results) - len(valid_results)} 条")