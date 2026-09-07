import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 기본 페이지 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 어제의 박스오피스")


# ---------------------------------------------------------
# 한국 시간 기준으로 '어제' 날짜 계산
# ---------------------------------------------------------
# 배포 서버가 한국 시간이 아닐 수 있으므로
# 반드시 Asia/Seoul 시간대를 지정합니다.
KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)
yesterday = now_kst.date() - timedelta(days=1)

# KOBIS API가 요구하는 YYYYMMDD 형식으로 변환
target_dt = yesterday.strftime("%Y%m%d")

st.caption(f"조회 기준일: {yesterday.strftime('%Y년 %m월 %d일')} (한국 시간)")


# ---------------------------------------------------------
# KOBIS API에서 일일 박스오피스 가져오기
# ---------------------------------------------------------
# @st.cache_data를 사용하면 같은 날짜를 다시 조회할 때
# API를 계속 호출하지 않고 캐시된 결과를 사용합니다.
#
# ttl=3600 → 1시간 동안 결과를 기억합니다.
@st.cache_data(ttl=3600)
def get_box_office(target_dt):
    # Streamlit Cloud의 Secrets에서 인증키를 가져옵니다.
    # 실제 인증키를 코드에 직접 적지 않습니다.
    api_key = st.secrets["KOBIS_KEY"]

    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_dt,
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10,
        )

        # HTTP 오류가 있으면 예외를 발생시킵니다.
        response.raise_for_status()

        # KOBIS가 JSON을 정상적으로 보내는지 확인합니다.
        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API에 접속하지 못했습니다.\n\n"
                f"상세 내용: {e}"
            ),
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API의 응답을 JSON으로 읽지 못했습니다.\n\n"
                "잠시 후 다시 시도하거나 KOBIS API 상태를 확인해 주세요."
            ),
        }

    # -----------------------------------------------------
    # 인증키 오류 등으로 faultInfo가 오는 경우
    # -----------------------------------------------------
    # KOBIS는 인증키가 틀려도 HTTP 상태코드가 200일 수 있습니다.
    # 따라서 상태코드만 보고 성공이라고 판단하면 안 됩니다.
    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        fault_code = fault_info.get("faultCode", "")
        fault_message = fault_info.get("message", "")

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 코드: {fault_code}\n"
                f"오류 내용: {fault_message}\n\n"
                "다음 항목을 확인해 주세요:\n"
                "• Streamlit Cloud의 Secrets에 KOBIS_KEY가 등록되어 있는지\n"
                "• 인증키를 정확하게 입력했는지\n"
                "• KOBIS Open API 사용 권한이 정상인지"
            ),
        }

    # -----------------------------------------------------
    # 정상적인 boxOfficeResult가 있는지 확인
    # -----------------------------------------------------
    box_office_result = data.get("boxOfficeResult")

    if not box_office_result:
        return {
            "success": False,
            "message": (
                "박스오피스 결과를 찾을 수 없습니다.\n\n"
                "KOBIS API 응답 구조와 API 상태를 확인해 주세요."
            ),
        }

    movie_list = box_office_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "message": (
                "조회된 영화 목록이 없습니다.\n\n"
                "다음 항목을 확인해 주세요:\n"
                "• 조회 날짜가 정상인지\n"
                "• KOBIS에서 해당 날짜의 박스오피스가 집계되었는지\n"
                "• KOBIS Open API가 정상적으로 응답하는지"
            ),
        }

    return {
        "success": True,
        "movies": movie_list,
    }


# ---------------------------------------------------------
# API 호출
# ---------------------------------------------------------
result = get_box_office(target_dt)


# ---------------------------------------------------------
# API 오류가 발생한 경우 안내 메시지 표시
# ---------------------------------------------------------
if not result["success"]:
    st.error(result["message"])
    st.stop()


movies = result["movies"]


# ---------------------------------------------------------
# 숫자로 사용할 값들을 문자열에서 숫자로 변환
# ---------------------------------------------------------
# KOBIS API는 숫자도 문자열로 보내므로
# 정렬과 그래프에 사용하기 전에 int로 변환합니다.
for movie in movies:
    movie["rank"] = int(movie.get("rank", 0))
    movie["audiCnt"] = int(movie.get("audiCnt", 0))
    movie["audiAcc"] = int(movie.get("audiAcc", 0))
    movie["scrnCnt"] = int(movie.get("scrnCnt", 0))
    movie["showCnt"] = int(movie.get("showCnt", 0))


# ---------------------------------------------------------
# 순위 기준으로 정렬
# ---------------------------------------------------------
movies.sort(key=lambda movie: movie["rank"])


# ---------------------------------------------------------
# 1위 영화 표시
# ---------------------------------------------------------
first_movie = movies[0]

st.subheader("🏆 1위 영화")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="오늘 관객수",
        value=f"{first_movie['audiCnt']:,}명",
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{first_movie['audiAcc']:,}명",
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{first_movie['scrnCnt']:,}개",
    )

st.markdown(f"### 🎞️ {first_movie['movieNm']}")


# ---------------------------------------------------------
# 관객수 상위 5편 막대그래프
# ---------------------------------------------------------
st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 순서대로 정렬합니다.
top5 = sorted(
    movies,
    key=lambda movie: movie["audiCnt"],
    reverse=True,
)[:5]

# Streamlit의 bar_chart가 사용할 데이터를 만듭니다.
chart_data = {
    movie["movieNm"]: movie["audiCnt"]
    for movie in top5
}

st.bar_chart(chart_data, x_label="영화", y_label="관객수")


# ---------------------------------------------------------
# 전체 박스오피스 표
# ---------------------------------------------------------
st.subheader("🎬 전체 박스오피스")

# 화면에 표시할 데이터만 따로 만듭니다.
table_data = []

for movie in movies:
    table_data.append(
        {
            "순위": movie["rank"],
            "영화명": movie["movieNm"],
            "개봉일": movie.get("openDt", ""),
            "관객수": movie["audiCnt"],
            "누적관객": movie["audiAcc"],
            "스크린수": movie["scrnCnt"],
        }
    )

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d",
        ),
        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%d명",
        ),
        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%d명",
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%d개",
        ),
    },
)
