from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List

import pandas as pd
import pydeck as pdk
import streamlit as st
from geopy.geocoders import Nominatim
from deep_translator import GoogleTranslator


st.set_page_config(page_title="Global Intel Dashboard", layout="wide")
if "lang" not in st.session_state:
    st.session_state.lang = "zh-CN"

I18N = {
    "zh-CN": {
        "title": "Global Intel Dashboard",
        "settings": "Settings",
        "toggle_lang": "切换语言 / Switch Language",
        "lang_label": "当前语言",
        "map_center": "地图中心",
        "category": "类别",
        "country": "国家/区域",
        "min_score": "最低影响分",
        "list": "资讯列表",
        "map_title": "3D 动态世界地图（事件分布）",
        "map_empty": "当前筛选条件下暂无地图数据。",
        "detail": "事件详情",
        "pick_event": "选择事件",
        "source_count": "来源数",
        "credibility": "可信度",
        "impact": "影响分",
        "sources": "来源列表",
        "timeline": "时间轴",
        "db_empty": "当前数据库无事件，请先执行 `python main.py`。",
        "time_window": "时间窗口（用于地图动态化）",
        "search": "搜索",
        "keyword_search": "关键词搜索",
        "date_search": "日期搜索",
        "translation": "翻译",
        "translated_title": "翻译标题",
        "original_title": "原始标题",
        "search_placeholder": "输入关键词搜索...",
        "start_date": "开始日期",
        "end_date": "结束日期",
        "enhanced_timeline": "增强时间轴",
        "related_events": "相关事件",
    },
    "en": {
        "title": "Global Intel Dashboard",
        "settings": "Settings",
        "toggle_lang": "Switch Language / 切换语言",
        "lang_label": "Current Language",
        "map_center": "Map Center",
        "category": "Category",
        "country": "Country/Region",
        "min_score": "Minimum Impact Score",
        "list": "News List",
        "map_title": "3D Dynamic World Map (Event Distribution)",
        "map_empty": "No map data under current filters.",
        "detail": "Event Detail",
        "pick_event": "Pick Event",
        "source_count": "Source Count",
        "credibility": "Credibility",
        "impact": "Impact Score",
        "sources": "Sources",
        "timeline": "Timeline",
        "db_empty": "No events in DB. Run `python main.py` first.",
        "time_window": "Time Window (map animation)",
        "search": "Search",
        "keyword_search": "Keyword Search",
        "date_search": "Date Search",
        "translation": "Translation",
        "translated_title": "Translated Title",
        "original_title": "Original Title",
        "search_placeholder": "Enter keywords to search...",
        "start_date": "Start Date",
        "end_date": "End Date",
        "enhanced_timeline": "Enhanced Timeline",
        "related_events": "Related Events",
    },
}

t = I18N[st.session_state.lang]
st.title(t["title"])
GEO_CACHE_PATH = Path("geo_cache.json")

# Track translation availability
if "translation_available" not in st.session_state:
    st.session_state.translation_available = True

@st.cache_data(show_spinner=False)
def translate_text(text: str, target_lang: str) -> str:
    """Translate text to target language"""
    if not st.session_state.translation_available:
        return text
        
    try:
        if not text or text.strip() == "":
            return text
        
        # Skip translation if already in target language
        if (target_lang == "zh-CN" and any('\u4e00' <= char <= '\u9fff' for char in text)) or \
           (target_lang == "en" and text.replace(' ', '').isascii()):
            return text
            
        translator = GoogleTranslator(source='auto', target=target_lang)
        result = translator.translate(text)
        return result
    except Exception as e:
        # Network error or other translation failure - mark as unavailable and return original text
        st.session_state.translation_available = False
        st.error(f"Translation unavailable: Cannot connect to translation service. Showing original text.")
        return text

def find_related_events(df: pd.DataFrame, current_event: str, category: str, country: str, threshold: int = 3) -> pd.DataFrame:
    """Find events related to the current event based on category, country, and keyword similarity"""
    related = df.copy()
    
    # Filter by same category or country
    if category and category != "all":
        related = related[related["category"] == category]
    if country and country != "all":
        related = related[related["country"] == country]
    
    # Remove the current event
    related = related[related["title"] != current_event]
    
    # Simple keyword matching (can be enhanced with more sophisticated NLP)
    current_words = set(current_event.lower().split())
    related["similarity_score"] = related["title"].apply(
        lambda x: len(set(x.lower().split()) & current_words)
    )
    
    # Return top related events
    return related.nlargest(threshold, "similarity_score")

def create_enhanced_timeline(timeline: List[Dict], related_events_df: pd.DataFrame) -> List[Dict]:
    """Create enhanced timeline with related events"""
    enhanced_timeline = timeline.copy()
    
    # Add related events to timeline
    for _, event in related_events_df.iterrows():
        event_timeline = json.loads(event["timeline_json"] or "[]")
        for point in event_timeline:
            point["related_event"] = event["title"]
            enhanced_timeline.append(point)
    
    # Sort by date
    enhanced_timeline.sort(key=lambda x: x.get("published_at", ""))
    
    return enhanced_timeline


@st.cache_data(show_spinner=False)
def load_events(db_path: str = "intel.db") -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            """
            SELECT event_id, title, category, country, source_count, credibility,
                   impact_score, risk_level, timeline_json, sources_json
            FROM events
            ORDER BY impact_score DESC
            """,
            conn,
        )
    finally:
        conn.close()
    return df


def _country_to_latlon(country: str) -> tuple[float, float]:
    mapping = {
        "china": (35.8, 104.2),
        "chinese": (35.8, 104.2),
        "global": (20.0, 0.0),
        "us": (37.1, -95.7),
        "usa": (37.1, -95.7),
        "united states": (37.1, -95.7),
        "uk": (54.0, -2.0),
        "united kingdom": (54.0, -2.0),
        "cn": (35.8, 104.2),
        "jp": (36.2, 138.2),
        "japan": (36.2, 138.2),
        "de": (51.2, 10.4),
        "germany": (51.2, 10.4),
        "fr": (46.2, 2.2),
        "france": (46.2, 2.2),
        "ru": (61.5, 105.3),
        "russia": (61.5, 105.3),
        "in": (20.6, 78.9),
        "india": (20.6, 78.9),
        "br": (-14.2, -51.9),
        "brazil": (-14.2, -51.9),
        "au": (-25.3, 133.8),
        "australia": (-25.3, 133.8),
        "za": (-30.6, 22.9),
        "south africa": (-30.6, 22.9),
    }
    return mapping.get((country or "").lower(), (20.0, 0.0))


def _load_geo_cache() -> dict[str, list[float]]:
    if not GEO_CACHE_PATH.exists():
        return {}
    try:
        with GEO_CACHE_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return {str(k): [float(v[0]), float(v[1])] for k, v in raw.items() if isinstance(v, list) and len(v) == 2}
    except Exception:
        return {}


def _save_geo_cache(cache: dict[str, list[float]]) -> None:
    with GEO_CACHE_PATH.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _geocode_country(country: str, cache: dict[str, list[float]], geocoder: Nominatim) -> tuple[float, float]:
    key = (country or "").strip().lower()
    if not key:
        return (20.0, 0.0)
    if key in cache:
        return (cache[key][0], cache[key][1])

    fallback_lat, fallback_lon = _country_to_latlon(key)
    if key in {"global", "world", "international"}:
        cache[key] = [fallback_lat, fallback_lon]
        return fallback_lat, fallback_lon

    try:
        location = geocoder.geocode(key, exactly_one=True, language="en")
        if location is not None:
            latlon = (float(location.latitude), float(location.longitude))
            cache[key] = [latlon[0], latlon[1]]
            return latlon
    except Exception:
        pass

    cache[key] = [fallback_lat, fallback_lon]
    return fallback_lat, fallback_lon


def _to_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


df = load_events()
if df.empty:
    st.warning(t["db_empty"])
    st.stop()

with st.expander(t["settings"], expanded=True):
    st.caption(f'{t["lang_label"]}: {st.session_state.lang.upper()}')
    if st.button(t["toggle_lang"]):
        st.session_state.lang = "en" if st.session_state.lang == "zh-CN" else "zh-CN"
        st.rerun()
    center_options = {
        "China / 中国": (35.8, 104.2, 2.4),
        "Global / 全球": (20.0, 0.0, 1.2),
        "US / 美国": (37.1, -95.7, 2.2),
        "Europe / 欧洲": (54.0, 15.0, 2.2),
        "Middle East / 中东": (29.0, 45.0, 2.4),
    }
    selected_center = st.selectbox(t["map_center"], list(center_options.keys()), index=0)

col1, col2, col3 = st.columns(3)
with col1:
    categories = ["all"] + sorted(df["category"].dropna().unique().tolist())
    selected_category = st.selectbox(t["category"], categories, index=0)
with col2:
    countries = ["all"] + sorted(df["country"].dropna().unique().tolist())
    selected_country = st.selectbox(t["country"], countries, index=0)
with col3:
    min_score = st.slider(t["min_score"], 0, 100, 0)

# Search functionality
st.subheader(t["search"])
search_col1, search_col2, search_col3 = st.columns(3)
with search_col1:
    keyword = st.text_input(t["keyword_search"], placeholder=t["search_placeholder"])
with search_col2:
    start_date = st.date_input(t["start_date"])
with search_col3:
    end_date = st.date_input(t["end_date"])

filtered = df.copy()
if selected_category != "all":
    filtered = filtered[filtered["category"] == selected_category]
if selected_country != "all":
    filtered = filtered[filtered["country"] == selected_country]
filtered = filtered[filtered["impact_score"] >= min_score]

# Apply search filters
if keyword:
    filtered = filtered[filtered["title"].str.contains(keyword, case=False, na=False)]

if start_date or end_date:
    filtered["timeline_data"] = filtered["timeline_json"].apply(lambda x: json.loads(x or "[]"))
    
    if start_date:
        start_date_str = start_date.strftime("%Y-%m-%d")
        filtered = filtered[
            filtered["timeline_data"].apply(
                lambda timeline: any(
                    point.get("published_at", "").startswith(start_date_str) 
                    for point in timeline
                )
            )
        ]
    
    if end_date:
        end_date_str = end_date.strftime("%Y-%m-%d")
        filtered = filtered[
            filtered["timeline_data"].apply(
                lambda timeline: any(
                    point.get("published_at", "").startswith(end_date_str) 
                    for point in timeline
                )
            )
        ]
    
    filtered = filtered.drop("timeline_data", axis=1)

st.subheader(t["list"])

# Add translation toggle (only show if translation is available)
show_translation = False
if st.session_state.translation_available:
    show_translation = st.checkbox(t["translation"])
else:
    st.info("Translation service unavailable due to network restrictions")

# Prepare display data
display_df = filtered[
    ["title", "category", "country", "impact_score", "risk_level", "credibility", "source_count"]
].copy()

if show_translation:
    target_lang = st.session_state.lang
    with st.spinner(t["translation"] + "..."):
        display_df[t["translated_title"]] = display_df["title"].apply(
            lambda x: translate_text(x, target_lang)
        )
    
    # Reorder columns to show translation
    cols = [t["translated_title"], t["original_title"]] if st.session_state.lang == "zh" else [t["translated_title"], t["original_title"]]
    display_df = display_df.rename(columns={"title": t["original_title"]})
    display_df = display_df[[cols[0], cols[1], "category", "country", "impact_score", "risk_level", "credibility", "source_count"]]

st.dataframe(display_df, use_container_width=True)

st.subheader(t["map_title"])
geo_cache = _load_geo_cache()
geo_dirty = False
geocoder = Nominatim(user_agent="global-intel-dashboard")
map_rows = []
for _, row in filtered.head(300).iterrows():
    cache_size_before = len(geo_cache)
    lat, lon = _geocode_country(str(row["country"]), geo_cache, geocoder)
    if len(geo_cache) != cache_size_before:
        geo_dirty = True
    timeline = json.loads(row["timeline_json"] or "[]")
    latest_time = timeline[-1]["published_at"] if timeline else ""
    map_rows.append(
        {
            "title": row["title"],
            "category": row["category"],
            "lat": lat,
            "lon": lon,
            "impact_score": float(row["impact_score"]),
            "published_at": latest_time,
        }
    )

if geo_dirty:
    _save_geo_cache(geo_cache)

map_df = pd.DataFrame(map_rows)
if not map_df.empty:
    map_df["published_dt"] = map_df["published_at"].apply(_to_dt)
    map_df = map_df[map_df["published_dt"].notna()]

    if not map_df.empty:
        min_time = map_df["published_dt"].min().to_pydatetime()
        max_time = map_df["published_dt"].max().to_pydatetime()
        cutoff = st.slider(t["time_window"], min_value=min_time, max_value=max_time, value=max_time)
        map_df = map_df[map_df["published_dt"] <= cutoff]

    layer = pdk.Layer(
        "ColumnLayer",
        data=map_df,
        get_position=["lon", "lat"],
        get_elevation="impact_score * 1000",
        elevation_scale=1,
        radius=120000,
        get_fill_color=[255, 80, 80, 180],
        pickable=True,
        auto_highlight=True,
    )
    center_lat, center_lon, center_zoom = center_options[selected_center]
    view_state = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=center_zoom, pitch=45)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text": "{title}\n{category}\nscore={impact_score}"}))
else:
    st.info(t["map_empty"])

st.subheader(t["detail"])
event_titles = filtered["title"].tolist()
selected_title = st.selectbox(t["pick_event"], event_titles, index=0)
selected_row = filtered[filtered["title"] == selected_title].iloc[0]

timeline = json.loads(selected_row["timeline_json"] or "[]")
sources = json.loads(selected_row["sources_json"] or "[]")

# Find related events
related_events = find_related_events(
    df, selected_title, 
    selected_row["category"], 
    selected_row["country"]
)

# Display event details with translation option
col1, col2 = st.columns(2)
with col1:
    st.write(f"**{t['original_title']}**: {selected_title}")
    if show_translation:
        target_lang = st.session_state.lang
        translated_title = translate_text(selected_title, target_lang)
        st.write(f"**{t['translated_title']}**: {translated_title}")

with col2:
    st.write(
        f"**{t['source_count']}**: {selected_row['source_count']} | "
        f"**{t['credibility']}**: {selected_row['credibility']} | "
        f"**{t['impact']}**: {selected_row['impact_score']}"
    )

st.write(f"**{t['sources']}**:", ", ".join(sources))

# Enhanced timeline
st.subheader(t["enhanced_timeline"])
enhanced_timeline = create_enhanced_timeline(timeline, related_events)

for point in enhanced_timeline:
    event_info = f" | **{t['related_events']}**: {point.get('related_event', '')}" if point.get('related_event') else ""
    st.write(f"- {point.get('published_at')} | {point.get('source_name')} | {point.get('article_url')}{event_info}")

# Show related events section
if not related_events.empty:
    st.subheader(t["related_events"])
    for _, event in related_events.iterrows():
        with st.expander(f"{event['title']} (Score: {event['impact_score']})"):
            st.write(f"**Category**: {event['category']}")
            st.write(f"**Country**: {event['country']}")
            st.write(f"**Impact Score**: {event['impact_score']}")
            if show_translation:
                target_lang = st.session_state.lang
                translated = translate_text(event['title'], target_lang)
                st.write(f"**{t['translated_title']}**: {translated}")
