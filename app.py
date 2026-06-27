import streamlit as st
import pandas as pd
import numpy as np
import io
import msoffcrypto
import re
from datetime import datetime

# 1. การตั้งค่าหน้าเว็บ
st.set_page_config(page_title="ระบบแปลงข้อมูล", layout="centered")

# 2. การตกแต่งด้วย CSS 
custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600&display=swap');
.stApp { background-color: #09101C; font-family: 'Kanit', sans-serif; }
h1, h2, h3 { color: #D0A83A !important; font-family: 'Kanit', sans-serif !important; font-weight: 500; }
p, label { color: #F8FAFC !important; font-family: 'Kanit', sans-serif !important; }
.stButton>button { background-color: #D0A83A !important; color: #000000 !important; border-radius: 5px; border: none; font-weight: 600; width: 100%; }
.stButton>button:hover { background-color: #E6C153 !important; }
[data-testid="stFileUploadDropzone"] { background-color: #131E32 !important; border: 2px dashed #D0A83A !important; }
[data-testid="stFileUploadDropzone"] * { color: #F8FAFC !important; }
.stSelectbox > div > div { background-color: #131E32 !important; border-color: #D0A83A !important; }
div[data-baseweb="select"] span { color: #F8FAFC !important; }
div[data-baseweb="popover"] ul li, div[data-baseweb="popover"] ul li span { color: #000000 !important; }
div[data-baseweb="popover"] ul li:hover { background-color: #E6C153 !important; color: #000000 !important; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# 3. ฐานข้อมูลรหัสผ่านมาตรฐาน
BANK_PASSWORDS = {
    "KBANK": "2533*",
    "SCB": "7512",
    "KTB": "1263",
    "BBL": None,
    "BAY": None,
    "TTB": None,
    "UOB": None,
    "CIMB": None,
    "TISCO": None,
    "KKP": None,
    "GSB": None,
    "BAAC": None,
    "GHB": None,
    "อื่นๆ": None
}

def decrypt_excel(file_bytes, password):
    decrypted_file = io.BytesIO()
    try:
        office_file = msoffcrypto.OfficeFile(file_bytes)
        office_file.load_key(password=password)
        office_file.decrypt(decrypted_file)
        decrypted_file.seek(0)
        return decrypted_file, True
    except Exception:
        return None, False

def convert_buddhist_year_string(dt):
    if pd.isna(dt) or str(dt).strip().lower() in ['nan', 'nat', 'none', '']: return dt 
    if isinstance(dt, (pd.Timestamp, datetime)): 
        dt_str = dt.strftime('%d/%m/%Y')
    else:
        dt_str = str(dt).strip()
    
    match = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', dt_str)
    if match:
        d = int(match.group(1))
        m = int(match.group(2))
        year_part = int(match.group(3))
        
        if year_part >= 2400: year_christian = year_part - 543
        elif 20 < year_part < 100: year_christian = 2000 + year_part
        else: year_christian = year_part
            
        return f"{d:02d}/{m:02d}/{year_christian}"
    return dt 

def process_kbank(excel_file):
    excel_data = pd.ExcelFile(excel_file)
    dtype_spec = {'หมายเลขบัญชีต้นทาง': str, 'หมายเลขบัญชีปลายทาง': str}
    df_for_clean = pd.read_excel(excel_data, sheet_name=0, header=3, dtype=dtype_spec)
    df_original_copy = pd.read_excel(excel_data, sheet_name=0, header=None)

    raw_cell_text = str(df_original_copy.iloc[1, 0]).strip() 
    
    def extract_account_number(text):
        text_cleaned = text.upper()
        if 'หมายเลขบัญชี' in text_cleaned: text_cleaned = text_cleaned.split('หมายเลขบัญชี', 1)[-1].strip()
        if ':' in text_cleaned: text_cleaned = text_cleaned.split(':', 1)[-1].strip()
        match = re.search(r'([\d-]{5,})', text_cleaned)
        if match: return match.group(0).replace('-', '').replace(' ', '').strip()
        return 'PARSE_ERROR'

    def extract_account_name(text):
        text_cleaned = str(text).upper().strip()
        if not text_cleaned or text_cleaned == 'NAN': return '' 
        match = re.search(r'(?:ชื่อบัญชี|ชื่อบัญชี\s*:\s*)(.*?)(?=สาขา|BRANCH)', text_cleaned, re.IGNORECASE)
        if match: return match.group(1).strip()
        if 'ชื่อบัญชี' in text_cleaned: return text_cleaned.split('ชื่อบัญชี', 1)[-1].strip().split(':', 1)[-1].strip()
        return '' 
        
    kbank_acc_num = extract_account_number(raw_cell_text)
    kbank_acc_name = extract_account_name(raw_cell_text)
    if not kbank_acc_name or kbank_acc_name in ['PARSE_ERROR', '']:
        kbank_acc_name = kbank_acc_num if kbank_acc_num != 'PARSE_ERROR' else 'KBANK_ACCOUNT'

    if 'วันที่ทำรายการ' in df_for_clean.columns:
        df_for_clean['วันที่ทำรายการ'] = df_for_clean['วันที่ทำรายการ'].apply(convert_buddhist_year_string)
        df_for_clean['วันที่ทำรายการ'] = pd.to_datetime(df_for_clean['วันที่ทำรายการ'], format='%d/%m/%Y', errors='coerce')

    if 'ฝากเงิน' in df_for_clean.columns and 'ประเภทรายการ' in df_for_clean.columns:
        is_acc_empty = df_for_clean['หมายเลขบัญชีต้นทาง'].apply(lambda x: str(x).strip() in ['', 'NAN', 'nan'])
        deposit_numeric = pd.to_numeric(df_for_clean['ฝากเงิน'], errors='coerce').fillna(0)
        mask_fill_type = is_acc_empty & (deposit_numeric != 0)
        df_for_clean.loc[mask_fill_type, 'หมายเลขบัญชีต้นทาง'] = df_for_clean['ประเภทรายการ']

    source_cols = ['ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง']
    if 'ถอนเงิน' in df_for_clean.columns:
        is_source_empty = df_for_clean[source_cols].apply(lambda col: col.astype(str).str.strip().eq('') | col.isna()).all(axis=1)
        withdraw_numeric = pd.to_numeric(df_for_clean['ถอนเงิน'], errors='coerce').fillna(0)
        mask_fill_source = is_source_empty & (withdraw_numeric != 0)
        df_for_clean.loc[mask_fill_source, ['ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง']] = ['KBANK', kbank_acc_num, kbank_acc_name]

    if 'ถอนเงิน' in df_for_clean.columns and 'ประเภทรายการ' in df_for_clean.columns:
        is_acc_empty_dest = df_for_clean['หมายเลขบัญชีปลายทาง'].apply(lambda x: str(x).strip() in ['', 'NAN', 'nan'])
        mask_fill_type_dest = is_acc_empty_dest & (withdraw_numeric != 0)
        df_for_clean.loc[mask_fill_type_dest, 'หมายเลขบัญชีปลายทาง'] = df_for_clean['ประเภทรายการ']

    dest_cols = ['ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง']
    if 'ฝากเงิน' in df_for_clean.columns:
        is_dest_empty = df_for_clean[dest_cols].apply(lambda col: col.astype(str).str.strip().eq('') | col.isna()).all(axis=1)
        mask_fill_dest = is_dest_empty & (deposit_numeric != 0)
        df_for_clean.loc[mask_fill_dest, ['ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง']] = ['KBANK', kbank_acc_num, kbank_acc_name]

    new_columns = ['วันที่ทำรายการ', 'เวลาที่ทำรายการ', 'ประเภทรายการ', 'ช่องทาง', 'ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง', 'ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง', 'ยอดเงิน', 'จำนวนครั้ง']
    df_cleaned = pd.DataFrame(columns=new_columns)
    
    for col in [c for c in new_columns if c not in ['ยอดเงิน', 'จำนวนครั้ง']]:
        if col in df_for_clean.columns:
            if col == 'วันที่ทำรายการ':
                df_for_clean[col] = df_for_clean[col].astype(object).where(pd.notna(df_for_clean[col]), '')
                df_cleaned[col] = df_for_clean[col]
            elif col in ['หมายเลขบัญชีต้นทาง', 'หมายเลขบัญชีปลายทาง']:
                df_cleaned[col] = df_for_clean[col].astype(str).str.replace(r'\.0$', '', regex=True)
            else:
                df_cleaned[col] = df_for_clean[col]

    if 'ฝากเงิน' in df_for_clean.columns and 'ถอนเงิน' in df_for_clean.columns:
        df_cleaned['ยอดเงิน'] = np.where(deposit_numeric != 0, deposit_numeric, withdraw_numeric)
        df_cleaned['_source_type'] = np.where(deposit_numeric != 0, 'DEPOSIT', 'WITHDRAW')
    else:
        df_cleaned['ยอดเงิน'] = 0 
        df_cleaned['_source_type'] = 'UNKNOWN'
        
    df_cleaned['จำนวนครั้ง'] = 1
    df_cleaned['ยอดเงิน'] = df_cleaned['ยอดเงิน'].replace([np.inf, -np.inf], np.nan)
    df_cleaned_ready = df_cleaned.fillna('') 
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_original_copy.to_excel(writer, sheet_name='Original', index=False, header=False)
        worksheet_cleaned = writer.book.add_worksheet('Cleaned Data')
        
        green_fmt = writer.book.add_format({'font_color': 'green', 'num_format': '#,##0.00'})
        red_fmt = writer.book.add_format({'font_color': 'red', 'num_format': '#,##0.00'})
        default_fmt = writer.book.add_format({'num_format': 'General'})
        date_fmt = writer.book.add_format({'num_format': 'dd/mm/yyyy'}) 
        txt_fmt = writer.book.add_format({'num_format': '@'})

        for col_num, value in enumerate(new_columns): worksheet_cleaned.write(0, col_num, value, default_fmt)

        for row_num, row_data in df_cleaned_ready.iterrows():
            source = row_data['_source_type']
            for col_num, col_name in enumerate(new_columns):
                cell_val = row_data[col_name]
                if col_name == 'ยอดเงิน':
                    fmt = green_fmt if source == 'DEPOSIT' else red_fmt
                    if cell_val != '' and pd.notna(cell_val): worksheet_cleaned.write_number(row_num + 1, col_num, cell_val, fmt)
                    else: worksheet_cleaned.write_blank(row_num + 1, col_num, '', default_fmt)
                elif col_name == 'วันที่ทำรายการ' and cell_val != '':
                    if isinstance(cell_val, (pd.Timestamp, datetime)): worksheet_cleaned.write_datetime(row_num + 1, col_num, cell_val, date_fmt)
                    else: worksheet_cleaned.write(row_num + 1, col_num, cell_val, default_fmt)
                elif col_name in ['หมายเลขบัญชีต้นทาง', 'หมายเลขบัญชีปลายทาง']:
                    worksheet_cleaned.write_string(row_num + 1, col_num, str(cell_val), txt_fmt)
                else:
                    worksheet_cleaned.write(row_num + 1, col_num, cell_val, default_fmt)
        worksheet_cleaned.autofit()
        
    return output.getvalue(), df_cleaned_ready

def process_ktb(excel_file, account_number, account_name):
    df_full_raw = pd.read_excel(excel_file, sheet_name=0, header=None)
    df_data_map = df_full_raw.copy()
    df_data_map.columns = df_data_map.iloc[0].astype(str).str.strip().str.replace(r'[\s\n-]', '', regex=True).str.lower()
    df_data_map = df_data_map[1:].reset_index(drop=True)
    
    new_columns = ['วันที่ทำรายการ', 'เวลาที่ทำรายการ', 'ประเภทรายการ', 'ช่องทาง', 'ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง', 'ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง', 'ยอดเงิน', 'จำนวนครั้ง']
    df_cleaned = pd.DataFrame(index=df_data_map.index, columns=new_columns)

    def force_clean_text(val):
        s = str(val).strip()
        return '' if s.lower() in ['nan', 'none', 'nat', ''] else s

    def pad_account_number(val):
        s = force_clean_text(val).split('.')[0]
        return s.zfill(10) if s.isdigit() else s

    df_cleaned['วันที่ทำรายการ'] = df_data_map.get('วันที่', pd.Series(dtype=str)).apply(convert_buddhist_year_string)
    df_cleaned['เวลาที่ทำรายการ'] = df_data_map.get('เวลา', pd.Series(dtype=str)).apply(force_clean_text)
    df_cleaned['ประเภทรายการ'] = df_data_map.get('รายการ', pd.Series(dtype=str)).apply(force_clean_text)
    df_cleaned['ช่องทาง'] = df_data_map.get('สถานที่', pd.Series(dtype=str)).apply(force_clean_text)

    try:
        df_cleaned['ชื่อธนาคารต้นทาง']    = df_full_raw.iloc[1:, 6].reset_index(drop=True).apply(force_clean_text)
        df_cleaned['หมายเลขบัญชีต้นทาง']  = df_full_raw.iloc[1:, 7].reset_index(drop=True).apply(pad_account_number)
        df_cleaned['ชื่อธนาคารปลายทาง']   = df_full_raw.iloc[1:, 8].reset_index(drop=True).apply(force_clean_text)
        df_cleaned['หมายเลขบัญชีปลายทาง'] = df_full_raw.iloc[1:, 9].reset_index(drop=True).apply(pad_account_number)
    except IndexError:
        df_cleaned[['ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง']] = ''

    df_cleaned['ชื่อบัญชีต้นทาง'] = ''
    df_cleaned['ชื่อบัญชีปลายทาง'] = ''
    df_cleaned['ยอดเงิน'] = pd.to_numeric(df_data_map.get('จำนวนเงิน', pd.Series([0]*len(df_data_map))), errors='coerce').fillna(0)
    df_cleaned['จำนวนครั้ง'] = 1

    cond_in = (df_cleaned['ประเภทรายการ'] == 'เงินโอนเข้า')
    df_cleaned.loc[cond_in, ['ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง', 'หมายเลขบัญชีต้นทาง']] = ['KTB', account_number, account_name, 'เงินโอนเข้า']
    cond_out = (df_cleaned['ประเภทรายการ'] == 'เงินโอนออก')
    df_cleaned.loc[cond_out, ['ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง', 'หมายเลขบัญชีปลายทาง']] = ['KTB', account_number, account_name, 'เงินโอนออก']
    cond_chq = (df_cleaned['ประเภทรายการ'] == 'ฝากเช็ค')
    df_cleaned.loc[cond_chq, ['ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง', 'หมายเลขบัญชีต้นทาง']] = ['KTB', account_number, account_name, 'ฝากเช็ค']
    cond_tr_out = (df_cleaned['ประเภทรายการ'] == 'โอนเงิน') & (df_cleaned['หมายเลขบัญชีต้นทาง'] == '') & (df_cleaned['หมายเลขบัญชีปลายทาง'] != '')
    df_cleaned.loc[cond_tr_out, ['ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง']] = ['KTB', account_number, account_name]
    cond_tr_in = (df_cleaned['ประเภทรายการ'] == 'โอนเงิน') & (df_cleaned['หมายเลขบัญชีปลายทาง'] == '') & (df_cleaned['หมายเลขบัญชีต้นทาง'] != '')
    df_cleaned.loc[cond_tr_in, ['ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง']] = ['KTB', account_number, account_name]
    cond_dep = (df_cleaned['ประเภทรายการ'] == 'ฝากเงิน')
    df_cleaned.loc[cond_dep, ['ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง', 'หมายเลขบัญชีต้นทาง']] = ['KTB', account_number, account_name, 'ฝากเงิน']
    cond_wit = (df_cleaned['ประเภทรายการ'] == 'ถอนเงิน')
    df_cleaned.loc[cond_wit, ['ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง', 'หมายเลขบัญชีปลายทาง']] = ['KTB', account_number, account_name, 'ถอนเงิน']
    cond_pay = (df_cleaned['ประเภทรายการ'] == 'ชำระเงิน')
    df_cleaned.loc[cond_pay, ['ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง', 'หมายเลขบัญชีปลายทาง']] = ['KTB', account_number, account_name, 'ชำระเงิน']

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_full_raw.to_excel(writer, sheet_name='Original', index=False, header=False)
        ws = writer.book.add_worksheet('Cleaned Data')
        
        fmt_head = writer.book.add_format({'bold': True, 'align': 'center', 'border': 1, 'bg_color': '#D9E1F2'})
        fmt_txt  = writer.book.add_format({'num_format': '@'}) 
        fmt_green = writer.book.add_format({'num_format': '#,##0.00', 'font_color': '#006400', 'bold': True})
        fmt_red   = writer.book.add_format({'num_format': '#,##0.00', 'font_color': '#FF0000', 'bold': True})
        fmt_normal = writer.book.add_format({'num_format': '#,##0.00'})
        fmt_date = writer.book.add_format({'num_format': '@', 'align': 'center'})

        for col, val in enumerate(df_cleaned.columns): ws.write(0, col, val, fmt_head)

        for r, row in df_cleaned.iterrows():
            acc_src = str(row['หมายเลขบัญชีต้นทาง']).strip()
            acc_dest = str(row['หมายเลขบัญชีปลายทาง']).strip()
            amount_fmt = fmt_normal
            if acc_src == account_number: amount_fmt = fmt_red
            elif acc_dest == account_number: amount_fmt = fmt_green

            for c, (col_name, val) in enumerate(row.items()):
                if col_name == 'ยอดเงิน': ws.write_number(r+1, c, float(val), amount_fmt)
                elif col_name == 'จำนวนครั้ง': ws.write_number(r+1, c, float(val), fmt_normal)
                elif col_name == 'วันที่ทำรายการ': ws.write_string(r+1, c, str(val), fmt_date)
                else: ws.write_string(r+1, c, force_clean_text(val), fmt_txt)
        ws.autofit()

    return output.getvalue(), df_cleaned

def process_general(excel_file):
    df_raw = pd.read_excel(excel_file)
    df_cleansed = df_raw.copy()
    if "Account_Number" in df_cleansed.columns:
        df_cleansed["Account_Number"] = df_cleansed["Account_Number"].astype(str).str.zfill(10)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_cleansed.to_excel(writer, index=False, sheet_name='Cleansed_Data')
    return output.getvalue(), df_cleansed

def process_and_allow_download(excel_file, bank_name, ktb_acc_num="", ktb_acc_name=""):
    st.write("---")
    st.subheader("3. การประมวลผล (Processing)")
    
    try:
        # **แก้ไขเงื่อนไขการตรวจสอบชื่อธนาคารตรงจุดนี้ครับ**
        if bank_name == "KBANK":  
            st.info("กำลังประมวลผลข้อมูลตามโครงสร้างของธนาคารกสิกรไทย (KBANK)...")
            processed_data, df_show = process_kbank(excel_file)
        elif bank_name == "KTB":
            if not ktb_acc_num or not ktb_acc_name:
                st.warning("ระบบไม่สามารถประมวลผลได้ กรุณากรอก 'หมายเลขบัญชีหลัก' และ 'ชื่อบัญชีหลัก' ด้านบนให้ครบถ้วน")
                return
            st.info("กำลังประมวลผลข้อมูลตามโครงสร้างของธนาคารกรุงไทย (KTB)...")
            processed_data, df_show = process_ktb(excel_file, ktb_acc_num, ktb_acc_name)
        else:
            st.info(f"กำลังประมวลผลข้อมูลโครงสร้างพื้นฐานสำหรับ {bank_name}...")
            processed_data, df_show = process_general(excel_file)

        st.write("ตัวอย่างข้อมูลที่ประมวลผลแล้ว (5 แถวแรก):")
        display_df = df_show.drop(columns=['_source_type']) if '_source_type' in df_show.columns else df_show
        st.dataframe(display_df.head())

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="ดาวน์โหลดไฟล์ Excel (Export)",
            data=processed_data,
            file_name=f"Cleaned_{bank_name}_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการประมวลผล: {e}")

def main():
    st.title("DATA CLEANSING SYSTEM")

    st.subheader("1. เลือกธนาคาร")
    selected_bank = st.selectbox("ระบุธนาคารเจ้าของไฟล์:", list(BANK_PASSWORDS.keys()))

    ktb_acc_num, ktb_acc_name = "", ""
    if selected_bank == "KTB":
        st.info("โปรดระบุข้อมูลบัญชีหลักเพื่อใช้ประมวลผลทิศทางการโอนเงิน และจัดรูปแบบสียอดเงิน")
        ktb_acc_num = st.text_input("หมายเลขบัญชีหลัก (10 หลัก):", max_chars=10)
        ktb_acc_name = st.text_input("ชื่อบัญชีหลัก:")

    st.subheader("2. นำเข้าข้อมูล (Import)")
    uploaded_file = st.file_uploader("ลากไฟล์ Excel มาวาง หรือคลิกเพื่อเลือกไฟล์ (รองรับสูงสุด 2GB)", type=['xlsx', 'xls'])

    if uploaded_file is not None:
        file_bytes = io.BytesIO(uploaded_file.read())
        is_encrypted = False
        
        try:
            pd.read_excel(file_bytes, nrows=1)
            file_bytes.seek(0)
        except Exception:
            try:
                file_bytes.seek(0)
                office_file = msoffcrypto.OfficeFile(file_bytes)
                is_encrypted = office_file.is_encrypted
            except Exception:
                is_encrypted = False

        if is_encrypted:
            st.warning("ตรวจพบการเข้ารหัสไฟล์ (Password Protected)")
            expected_password = BANK_PASSWORDS.get(selected_bank)

            if expected_password:
                st.info(f"รหัสผ่านที่คาดการณ์สำหรับ {selected_bank} คือ: {expected_password}")
                if st.button("ดำเนินการปลดรหัสผ่าน"):
                    decrypted_file, success = decrypt_excel(file_bytes, expected_password)
                    if success:
                        st.success("ปลดรหัสผ่านสำเร็จ")
                        process_and_allow_download(decrypted_file, selected_bank, ktb_acc_num, ktb_acc_name)
                    else:
                        st.error("รหัสผ่านไม่ถูกต้อง กรุณาดำเนินการปลดรหัสด้วยตนเอง")
            else:
                st.error("ไม่ทราบรหัสผ่านสำหรับธนาคารนี้ กรุณาดำเนินการปลดรหัสด้วยตนเอง")
        else:
            st.success("ไฟล์พร้อมดำเนินการ (ไม่มีการเข้ารหัส)")
            file_bytes.seek(0)
            process_and_allow_download(file_bytes, selected_bank, ktb_acc_num, ktb_acc_name)

if __name__ == "__main__":
    main()
