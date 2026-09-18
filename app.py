"""
Erasmus Guide — web arayüzü.

Çalıştırmak için:  streamlit run app.py
"""

import os

import pandas as pd
import streamlit as st

import store
from agent import (
    EXAM_DATE,
    RUBRIC_CRITERIA,
    context_report,
    current_phase,
    make_exercise,
    make_plan,
    score_essay,
)
from datetime import date

st.set_page_config(page_title="Erasmus Guide", page_icon="📝", layout="wide")

CRITERIA_LABELS = dict(RUBRIC_CRITERIA)

# --- kenar çubuğu ----------------------------------------------------------

with st.sidebar:
    st.header("Erasmus Guide")
    kalan = (EXAM_DATE - date.today()).days
    st.metric("Sınava kalan", f"{kalan} gün")
    st.caption(current_phase())

    gecmis = store.history()
    if gecmis:
        st.metric("Değerlendirilen essay", len(gecmis))
        st.metric("Son puan", f"{gecmis[0]['total']}/50")

    zayif = store.weakest_criteria()
    if zayif:
        st.write("**En zayıf alanlar**")
        for key, ort in zayif[:3]:
            st.caption(f"{CRITERIA_LABELS.get(key, key)} — {ort:.1f}/10")

    if not os.environ.get("GEMINI_API_KEY"):
        st.error("GEMINI_API_KEY tanımlı değil.")

# --- sekmeler --------------------------------------------------------------

sekme1, sekme2, sekme3, sekme4 = st.tabs(
    ["Essay Değerlendirme", "Çalışma Planı", "Alıştırma", "İlerleme"]
)


# --- 1. essay --------------------------------------------------------------

with sekme1:
    st.subheader("Essay Değerlendirme")
    st.caption("50 puan, 5 kriter. Her değerlendirme aynı biçimde döner ve kaydedilir.")

    konu = st.text_input("Essay konusu", placeholder="Örn: Should universities be free?")
    metin = st.text_area("Essay metni", height=300, placeholder="Essay'ini buraya yapıştır…")

    if metin:
        st.caption(f"{len(metin.split())} kelime (hedef: 300-500)")

    if st.button("Değerlendir", type="primary", disabled=not metin.strip()):
        with st.spinner("Rubriğe göre değerlendiriliyor…"):
            try:
                puan = score_essay(metin, konu)
                store.save_essay(konu, metin, puan)
                st.session_state["son_puan"] = puan
            except Exception as hata:
                st.error(f"Değerlendirme başarısız: {hata}")

    puan = st.session_state.get("son_puan")
    if puan:
        st.metric("Toplam", f"{puan.total}/50")

        satirlar = [
            {
                "Kriter": etiket,
                "Puan": f"{puan.criteria.get(anahtar, {}).get('score', 0)}/10",
                "Gerekçe": puan.criteria.get(anahtar, {}).get("comment", ""),
            }
            for anahtar, etiket in RUBRIC_CRITERIA
        ]
        st.dataframe(pd.DataFrame(satirlar), use_container_width=True, hide_index=True)

        if puan.priority:
            st.info(f"**Bir sonraki essay'de tek odak:** {puan.priority}")

        st.write("**Cümle düzeltmeleri**")
        for i, d in enumerate(puan.corrections, 1):
            with st.expander(f"{i}. {d.get('original', '')[:70]}…"):
                st.write("**Özgün:**", d.get("original", ""))
                st.write("**Düzeltilmiş:**", d.get("revised", ""))
                st.caption(d.get("why", ""))

        if puan.strengths:
            st.write("**İyi olan yanlar**")
            for g in puan.strengths:
                st.write("-", g)


# --- 2. plan ---------------------------------------------------------------

with sekme2:
    st.subheader("Haftalık Çalışma Planı")
    st.caption(f"Plan bulunulan faza göre üretilir — {current_phase()}")

    sutun1, sutun2 = st.columns(2)
    saat = sutun1.slider("Bu hafta ayırabileceğin süre (saat)", 1, 20, 6)
    zayif_alan = sutun2.text_input("Zorlandığın alan", placeholder="Örn: listening, essay girişi")

    if st.button("Plan üret", type="primary"):
        with st.spinner("Plan hazırlanıyor…"):
            try:
                st.markdown(make_plan(zayif_alan, saat, store.history()))
            except Exception as hata:
                st.error(f"Plan üretilemedi: {hata}")


# --- 3. alıştırma ----------------------------------------------------------

with sekme3:
    st.subheader("Alıştırma Üret")

    tur = st.radio(
        "Ne üretilsin?",
        ["reading", "essay", "listening"],
        format_func=lambda x: {
            "reading": "Reading — 10 paragraf, 10 boşluk",
            "essay": "Essay sorusu ve yapı rehberi",
            "listening": "Listening kaynak önerisi",
        }[x],
        horizontal=True,
    )

    if tur == "listening":
        st.caption(
            "Bu modda transkript üretilmez. Model üretimi metin gerçek konuşmanın "
            "hızını ve aksanını taşımadığı için gerçek kaynak önerilir."
        )

    if st.button("Üret", type="primary"):
        with st.spinner("Hazırlanıyor…"):
            try:
                st.markdown(make_exercise(tur))
            except Exception as hata:
                st.error(f"Üretilemedi: {hata}")


# --- 4. ilerleme -----------------------------------------------------------

with sekme4:
    st.subheader("İlerleme")
    gecmis = store.history()

    if not gecmis:
        st.info("Henüz değerlendirilmiş essay yok. İlk sekmeden bir essay gönder.")
    else:
        seri = pd.DataFrame(
            [
                {"Tarih": g["created_at"][:10], "Toplam": g["total"]}
                for g in reversed(gecmis)
            ]
        )
        st.line_chart(seri, x="Tarih", y="Toplam", height=260)

        st.write("**Kriter ortalamaları**")
        ort = store.weakest_criteria(limit=20)
        st.dataframe(
            pd.DataFrame(
                [{"Kriter": CRITERIA_LABELS.get(k, k), "Ortalama": round(v, 1)} for k, v in ort]
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.write("**Geçmiş essayler**")
        for g in gecmis:
            with st.expander(f"{g['created_at'][:16]} — {g['total']}/50 — {g['topic'] or 'konusuz'}"):
                st.caption(f"{g['word_count']} kelime")
                if g["priority"]:
                    st.caption(f"Odak: {g['priority']}")
                st.text(g["essay_text"][:1200])
                if st.button("Sil", key=f"sil{g['id']}"):
                    store.delete_essay(g["id"])
                    st.rerun()

# --- altbilgi --------------------------------------------------------------

st.divider()
_dosyalar, _yuklenen, _toplam = context_report("feedback")
st.caption(
    f"Essay değerlendirmede yüklenen referans: {', '.join(_dosyalar)} "
    f"({_yuklenen:,} / {_toplam:,} karakter). Her mod yalnızca ihtiyaç duyduğu "
    f"dosyaları yükler."
)
