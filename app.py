import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
import json
import os
import tempfile
from datetime import datetime

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="SOAP Asistanı Pro", page_icon="🩺", layout="wide")

# --- HAFIZA (SESSION STATE) AYARLARI ---
# Sayfa yenilense bile verilerin kaybolmaması için hafıza oluşturuyoruz
if "rapor_verisi" not in st.session_state:
    st.session_state.rapor_verisi = None
if "tarih_damgasi" not in st.session_state:
    st.session_state.tarih_damgasi = None

# --- PDF OLUŞTURMA FONKSİYONU ---
def pdf_olustur(veri, tarih):
    pdf = FPDF()
    pdf.add_page()

    # Türkçe karakter destekli standart font kullanımı
    pdf.add_font("Arial", "", "arial.ttf", uni=True) 
    # Not: Replit'te arial.ttf yoksa standart helvetica kullanır, 
    # basitlik için yerleşik fontu Türkçe karakterleri düzcelterek kullanıyoruz.
    pdf.set_font("helvetica", size=16, style="B")

    pdf.cell(200, 10, txt="TIBBI DEGERLENDIRME RAPORU (SOAP)", ln=True, align='C')
    pdf.set_font("helvetica", size=10)
    pdf.cell(200, 10, txt=f"Tarih: {tarih}", ln=True, align='C')
    pdf.line(10, 30, 200, 30)

    pdf.set_font("helvetica", size=12, style="B")
    pdf.cell(200, 10, txt="S - SUBJEKTIF (Hastanin Ifadeleri)", ln=True)
    pdf.set_font("helvetica", size=11)
    pdf.multi_cell(0, 8, txt=f"Sikayet: {veri['S']['sikayet']}\nOyku: {veri['S']['oyku']}\nOzgecmis: {veri['S']['ozgecmis']}")

    pdf.set_font("helvetica", size=12, style="B")
    pdf.cell(200, 10, txt="O - OBJEKTIF (Yasamsal Bulgular & Muayene)", ln=True)
    pdf.set_font("helvetica", size=11)

    # Vitals PDF kısmı
    vitals = veri['Vitals']
    v_metin = ""
    for anahtar, deger in vitals.items():
        v_metin += f"{anahtar.capitalize()}: {deger['deger'] if deger['deger'] else 'Belirtilmedi'} \n"

    pdf.multi_cell(0, 8, txt=v_metin + f"\nFizik Muayene: {veri['O']['fizik_muayene']}")

    pdf.set_font("helvetica", size=12, style="B")
    pdf.cell(200, 10, txt="A - DEGERLENDIRME", ln=True)
    pdf.set_font("helvetica", size=11)
    pdf.multi_cell(0, 8, txt=f"On Tani: {veri['A']['on_tani']}")

    pdf.set_font("helvetica", size=12, style="B")
    pdf.cell(200, 10, txt="P - PLAN", ln=True)
    pdf.set_font("helvetica", size=11)
    pdf.multi_cell(0, 8, txt=f"Plan: {veri['P']['plan']}")

    # PDF'i geçici dosyaya kaydet
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(temp_pdf.name)
    return temp_pdf.name

# --- ARAYÜZ TASARIMI ---
st.title("🎙️ Akıllı SOAP Asistanı")

# Üst Butonlar
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("➕ Yeni Hasta Kaydı Oluştur", use_container_width=True):
        st.session_state.rapor_verisi = None
        st.session_state.tarih_damgasi = None
        st.rerun()

with col2:
    api_key = st.text_input("Google Gemini API Anahtarı:", type="password", placeholder="AIzaSy...")

st.divider()

# Tarih Damgası
if st.session_state.tarih_damgasi:
    st.info(f"📅 Kayıt Zamanı: {st.session_state.tarih_damgasi}")

# Ses Kayıt Modülü (Streamlit yerleşik özelliği)
st.write("### 🎤 Yeni Ses Kaydı veya Ekleme Yap")
ses_dosyasi = st.audio_input("Konuşmak için mikrofona tıklayın:")

if ses_dosyasi and api_key:
    if st.button("Sesi Analiz Et ve Formu Doldur", type="primary"):
        try:
            genai.configure(api_key=api_key)
            st.session_state.tarih_damgasi = datetime.now().strftime("%d %B %Y - %H:%M")

            with st.spinner("Yapay zeka sesinizi analiz edip formu dolduruyor..."):
                # Sesi geçici dosyaya kaydet
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                    tmp_file.write(ses_dosyasi.getvalue())
                    tmp_file_path = tmp_file.name

                audio_file = genai.upload_file(path=tmp_file_path)

                # Zekadan JSON formatında yapılandırılmış veri istiyoruz
                prompt = """
                Aşağıdaki doktor ses kaydını dinle. Duyduğun bilgileri SOAP formatında aşağıdaki JSON şablonuna tam uyacak şekilde çıkar.
                Eğer bir bilgi geçmiyorsa değerine "Belirtilmedi" yaz. Yaşamsal bulgular (Vitals) için sayısal değerleri çıkar.
                Eğer sayısal değer normalse "durum": 0, hafif sapmaysa 1, orta sapmaysa 2, çok riskli sapmaysa 3 yaz. Değer yoksa null ve 0 yap.

                JSON Şablonu:
                {
                  "S": {"sikayet": "", "oyku": "", "ozgecmis": ""},
                  "O": {"fizik_muayene": ""},
                  "A": {"on_tani": ""},
                  "P": {"plan": ""},
                  "Vitals": {
                    "ates": {"deger": null, "durum": 0},
                    "nabiz": {"deger": null, "durum": 0},
                    "tansiyon": {"deger": null, "durum": 0},
                    "solunum": {"deger": null, "durum": 0}
                  }
                }
                Sadece bu JSON'ı döndür, başka açıklama yazma.
                """

                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content([prompt, audio_file])

                # JSON metnini temizle ve parse et
                json_metin = response.text.replace("```json", "").replace("```", "").strip()
                st.session_state.rapor_verisi = json.loads(json_metin)

                os.remove(tmp_file_path)
                st.rerun() # Sayfayı güncel formla yenile

        except Exception as e:
            st.error(f"Bir hata oluştu: {e}")

# --- FORM VE SONUÇ GÖSTERİMİ ---
if st.session_state.rapor_verisi:
    veri = st.session_state.rapor_verisi
    st.markdown("## 📋 Yapılandırılmış SOAP Raporu")

    # S - Subjektif
    st.markdown("### S - Subjektif")
    st.text_area("Ana Şikayet", veri['S']['sikayet'], disabled=True)
    st.text_area("Hastalık Öyküsü", veri['S']['oyku'], disabled=True)
    st.text_area("Özgeçmiş & Alerjiler", veri['S']['ozgecmis'], disabled=True)

    # O - Objektif & Vitals
    st.markdown("### O - Objektif (Yaşamsal Bulgular)")

    # Renk algoritması kutuları
    vcols = st.columns(4)
    vital_isimleri = ["ates", "nabiz", "tansiyon", "solunum"]
    vital_basliklari = ["Ateş (°C)", "Nabız (bpm)", "Tansiyon", "Solunum"]

    for i, (isim, baslik) in enumerate(zip(vital_isimleri, vital_basliklari)):
        deger = veri['Vitals'][isim]['deger']
        durum = veri['Vitals'][isim]['durum']

        # Senin istediğin renk mantığı!
        if deger is None or deger == "Belirtilmedi":
            bg_color = "#e0e0e0" # Açık Gri
            text = "BELİRTİLMEDİ"
        elif durum == 0:
            bg_color = "#d4edda" # Yeşil (Normal)
            text = str(deger)
        elif durum == 1:
            bg_color = "#ffcccc" # Açık Kırmızı
            text = str(deger)
        elif durum == 2:
            bg_color = "#ff6666" # Orta Kırmızı
            text = str(deger)
        else:
            bg_color = "#cc0000" # Koyu Kırmızı (Riskli)
            text = str(deger)

        with vcols[i]:
            st.markdown(
                f"<div style='background-color: {bg_color}; padding: 15px; border-radius: 10px; text-align: center; color: {'white' if durum >=3 else 'black'};'>"
                f"<b>{baslik}</b><br><span style='font-size: 20px;'>{text}</span></div>", 
                unsafe_allow_html=True
            )

    st.text_area("Fizik Muayene", veri['O']['fizik_muayene'], disabled=True)

    # A - Değerlendirme
    st.markdown("### A - Değerlendirme")
    st.text_input("Ön Tanı / Ayırıcı Tanı", veri['A']['on_tani'], disabled=True)

    # P - Plan
    st.markdown("### P - Plan")
    st.text_area("Tetkik ve Tedavi Planı", veri['P']['plan'], disabled=True)

    # --- PDF İNDİRME BUTONU ---
    st.markdown("---")
    pdf_yolu = pdf_olustur(veri, st.session_state.tarih_damgasi)
    with open(pdf_yolu, "rb") as pdf_dosyasi:
        st.download_button(
            label="📄 Raporu PDF Olarak İndir",
            data=pdf_dosyasi,
            file_name=f"SOAP_Raporu_{st.session_state.tarih_damgasi.replace(' ', '_')}.pdf",
            mime="application/pdf",
            type="primary"
        )
