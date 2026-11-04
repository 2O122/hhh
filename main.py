import re
from itertools import combinations
import pandas as pd
import plotly.express as px
import streamlit as st


@st.cache_data
def load_and_process_data(url):
    df = pd.read_csv(url, encoding="utf-8")

    # 괄호 및 괄호 안 내용 제거 및 세로줄(|) 기준 분리
    baskets = []
    all_menus = set()

    for raw_menu in df["메뉴"].dropna():
        cleaned_menu = re.sub(r"\(.*?\)", "", str(raw_menu))
        items = [
            item.strip() for item in cleaned_menu.split("|") if item.strip()
        ]
        # 한 식단 내 중복 메뉴 제거
        items = list(set(items))
        if items:
            baskets.append(items)
            all_menus.update(items)

    total_baskets = len(baskets)

    # 단일 항목 빈도 계산
    item_counts = {}
    for basket in baskets:
        for item in basket:
            item_counts[item] = item_counts.get(item, 0) + 1

    # 동시 출현 쌍 빈도 계산 (A, B)
    pair_counts = {}
    for basket in baskets:
        if len(basket) >= 2:
            for item1, item2 in combinations(sorted(basket), 2):
                pair_counts[(item1, item2)] = (
                    pair_counts.get((item1, item2), 0) + 1
                )

    # 규칙 생성 (A -> B 및 B -> A)
    rules_data = []
    for (item1, item2), co_occur in pair_counts.items():
        # A -> B
        supp_A_B = co_occur / total_baskets
        conf_A_B = co_occur / item_counts[item1]
        lift_A_B = conf_A_B / (item_counts[item2] / total_baskets)
        rules_data.append(
            {
                "조건": item1,
                "결과": item2,
                "동시": co_occur,
                "지지도": round(supp_A_B, 4),
                "신뢰도": round(conf_A_B, 4),
                "향상도": round(lift_A_B, 4),
            }
        )

        # B -> A
        conf_B_A = co_occur / item_counts[item2]
        lift_B_A = conf_B_A / (item_counts[item1] / total_baskets)
        rules_data.append(
            {
                "조건": item2,
                "결과": item1,
                "동시": co_occur,
                "지지도": round(supp_A_B, 4),
                "신뢰도": round(conf_B_A, 4),
                "향상도": round(lift_B_A, 4),
            }
        )

    rules_df = pd.DataFrame(rules_data)
    unique_pairs_count = len(pair_counts)

    return (
        rules_df,
        total_baskets,
        len(all_menus),
        unique_pairs_count,
        sorted(list(all_menus)),
        item_counts,
        pair_counts,
    )


# 페이지 기본 설정
st.set_page_config(page_title="급식 규칙 찾기", layout="wide")
st.title("🍱 급식 연관 규칙 찾기")

DATA_URL = "https://raw.githubusercontent.com/it-teacher-go/data-share-/main/songtan_meals_184.csv"

# 데이터 로드
try:
    (
        rules_df,
        total_days,
        total_menu_types,
        pair_count,
        menu_list,
        item_counts,
        pair_counts,
    ) = load_and_process_data(DATA_URL)
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()

# 정보 요약 한 줄 출력
st.markdown(
    f"**급식 일수:** {total_days}일 | **메뉴 종류 수:** {total_menu_types}개 | **함께 나온 적이 있는 메뉴 쌍의 수:** {pair_count}쌍"
)
st.divider()

# 컨트롤 영역
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    selected_menu = st.selectbox(
        "메뉴 선택 (해당 메뉴가 포함된 규칙만 조회):",
        options=["전체 보기"] + menu_list,
    )

with col2:
    sort_option = st.selectbox(
        "정렬 기준 선택:", options=["향상도 순", "신뢰도 순", "동시 순"]
    )

with col3:
    min_co_occur = st.slider(
        "최소 동시 출현 일수:", min_value=1, max_value=10, value=1
    )

# 데이터 필터링 (메뉴 선택 & 최소 동시 일수 조건)
filtered_df = rules_df[rules_df["동시"] >= min_co_occur].copy()

if selected_menu != "전체 보기":
    filtered_df = filtered_df[
        (filtered_df["조건"] == selected_menu)
        | (filtered_df["결과"] == selected_menu)
    ]

# 남은 규칙 개수 안내
st.info(f"💡 현재 설정 조건에 해당하는 규칙 수: **{len(filtered_df)}개**")

# 데이터 정렬
sort_mapping = {
    "향상도 순": "향상도",
    "신뢰도 순": "신뢰도",
    "동시 순": "동시",
}
sort_column = sort_mapping[sort_option]
filtered_df = filtered_df.sort_values(
    by=[sort_column, "동시"], ascending=False
).reset_index(drop=True)

# 시각화: 향상도 상위 10개 가로 막대그래프
st.subheader("📊 향상도 상위 10개 규칙")
if not filtered_df.empty:
    top10_df = (
        filtered_df.sort_values(by="향상도", ascending=False)
        .head(10)
        .copy()
    )
    top10_df["규칙"] = top10_df["조건"] + " ➔ " + top10_df["결과"]
    top10_df = top10_df.sort_values(by="향상도", ascending=True)

    fig = px.bar(
        top10_df,
        x="향상도",
        y="규칙",
        orientation="h",
        text="향상도",
        title="향상도 Top 10 규칙",
        color="향상도",
        color_continuous_scale="Viridis",
    )
    fig.update_layout(height=400, yaxis_title="규칙 (조건 ➔ 결과)")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("조건에 맞는 규칙이 없습니다.")

# 표 출력
st.subheader("📋 연관 규칙 목록")
st.dataframe(filtered_df, use_container_width=True)

st.divider()

# 함께 나온 적 없는 짝 기능
st.subheader("🔍 함께 나온 적 없는 짝 탐색")

target_menu = st.selectbox(
    "조회할 대상 메뉴를 선택하세요 (함께 나온 적 없는 메뉴 탐색용):",
    options=menu_list,
    key="unpaired_menu_select",
)

target_days = item_counts.get(target_menu, 0)
st.write(f"📌 **선택한 메뉴 '{target_menu}'이(가) 나온 일수:** {target_days}일")

# 함께 나온 메뉴 집합 생성
co_occurred_menus = set()
for (m1, m2), count in pair_counts.items():
    if count > 0:
        if m1 == target_menu:
            co_occurred_menus.add(m2)
        elif m2 == target_menu:
            co_occurred_menus.add(m1)

# 한번도 같이 안 나왔으면서 단독으로 10일 이상 나온 메뉴 추출
unpaired_data = []
for menu, count in item_counts.items():
    if menu != target_menu and menu not in co_occurred_menus and count >= 10:
        unpaired_data.append({"메뉴": menu, "단독 출현 일수": count})

unpaired_df = pd.DataFrame(unpaired_data)

if not unpaired_df.empty:
    unpaired_df = unpaired_df.sort_values(
        by="단독 출현 일수", ascending=False
    ).reset_index(drop=True)
    st.write("▼ **한 번도 함께 나오지 않았고, 단독으로는 10일 이상 나온 메뉴 목록**")
    st.dataframe(unpaired_df, use_container_width=True)
else:
    st.write("해당하는 메뉴가 없습니다.")
