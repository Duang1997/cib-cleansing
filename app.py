import streamlit as st
import pandas as pd
import numpy as np
import io
import msoffcrypto
import re
from datetime import datetime
import difflib

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
    "ธนาคารกสิกรไทย (KBANK)": "2533*",
    "ธนาคารกรุงไทย (KTB)": "1263",
    "ธนาคารไทยพาณิชย์ (SCB)": "7512",
    "ธนาคารทหารไทยธนชาต (TTB)": "Ttb@011",
    "ธนาคารกรุงเทพ (BBL)": None,
    "ธนาคารออมสิน (GSB)": None,
    "ระบบประสาน (PRASAN)": None
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

# ==========================================
# ระบบตรวจสอบและแก้ไขหัวตารางอัตโนมัติ (Fuzzy Matching)
# ==========================================
def fix_and_validate_headers(df, expected_headers):
    current_columns = df.columns.tolist()
    mapping = {}
    missing = []
    renamed_info = []

    def normalize(s):
        return str(s).replace(' ', '').replace('\n', '').replace('-', '').lower()

    norm_current = {normalize(c): c for c in current_columns if str(c).strip() != ''}

    for ex in expected_headers:
        n_ex = normalize(ex)
        if n_ex in norm_current:
            mapping[norm_current[n_ex]] = ex
        else:
            matches = difflib.get_close_matches(n_ex, norm_current.keys(), n=1, cutoff=0.6)
            if matches:
                matched_col = norm_current[matches[0]]
                mapping[matched_col] = ex
                renamed_info.append(f"[{matched_col}] ➔ [{ex}]")
            else:
                missing.append(ex)

    if mapping:
        df.rename(columns=mapping, inplace=True)

    return missing, renamed_info

def convert_buddhist_year_string(dt):
    if pd.isna(dt) or str(dt).strip().lower() in ['nan', 'nat', 'none', '']: return dt 
    if isinstance(dt, (pd.Timestamp, datetime)): 
        dt_str = dt.strftime('%d/%m/%Y')
    else:
        dt_str = str(dt).strip()
    match = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', dt_str)
    if match:
        d, m, year_part = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if year_part >= 2400: year_christian = year_part - 543
        elif 20 < year_part < 100: year_christian = 2000 + year_part
        else: year_christian = year_part
        return f"{d:02d}/{m:02d}/{year_christian}"
    return dt 

# ==========================================
# ส่วนประมวลผล KBANK
# ==========================================
def process_kbank(excel_file):
    excel_data = pd.ExcelFile(excel_file)
    dtype_spec = {'หมายเลขบัญชีต้นทาง': str, 'หมายเลขบัญชีปลายทาง': str}
    df_for_clean = pd.read_excel(excel_data, sheet_name=0, header=3, dtype=dtype_spec)
    df_original_copy = pd.read_excel(excel_data, sheet_name=0, header=None)

    expected_headers = ['วันที่ทำรายการ', 'ประเภทรายการ', 'ฝากเงิน', 'ถอนเงิน']
    missing, renamed = fix_and_validate_headers(df_for_clean, expected_headers)
    
    if missing:
        raise ValueError(f"⚠️ รูปแบบหัวตารางไม่ถูกต้อง! \nระบบต้องการคอลัมน์: {', '.join(missing)} \nกรุณาแก้ไขชื่อหัวตารางในไฟล์ Excel ให้ตรงตามรูปแบบก่อนทำรายการ")
    
    warn_msg = "ระบบได้ทำการปรับแก้หัวตารางอัตโนมัติ:\n" + " | ".join(renamed) if renamed else ""

    raw_cell_text = str(df_original_copy.iloc[1, 0]).strip() 
    def extract_account_number(text):
        t = text.upper()
        if 'หมายเลขบัญชี' in t: t = t.split('หมายเลขบัญชี', 1)[-1].strip()
        if ':' in t: t = t.split(':', 1)[-1].strip()
        match = re.search(r'([\d-]{5,})', t)
        return match.group(0).replace('-', '').replace(' ', '').strip() if match else 'PARSE_ERROR'

    def extract_account_name(text):
        t = str(text).upper().strip()
        if not t or t == 'NAN': return '' 
        match = re.search(r'(?:ชื่อบัญชี|ชื่อบัญชี\s*:\s*)(.*?)(?=สาขา|BRANCH)', t, re.IGNORECASE)
        if match: return match.group(1).strip()
        if 'ชื่อบัญชี' in t: return t.split('ชื่อบัญชี', 1)[-1].strip().split(':', 1)[-1].strip()
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

    if 'ถอนเงิน' in df_for_clean.columns:
        source_cols = ['ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง']
        is_source_empty = df_for_clean[source_cols].apply(lambda col: col.astype(str).str.strip().eq('') | col.isna()).all(axis=1)
        withdraw_numeric = pd.to_numeric(df_for_clean['ถอนเงิน'], errors='coerce').fillna(0)
        mask_fill_source = is_source_empty & (withdraw_numeric != 0)
        df_for_clean.loc[mask_fill_source, ['ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง']] = ['KBANK', kbank_acc_num, kbank_acc_name]

        if 'ประเภทรายการ' in df_for_clean.columns:
            is_acc_empty_dest = df_for_clean['หมายเลขบัญชีปลายทาง'].apply(lambda x: str(x).strip() in ['', 'NAN', 'nan'])
            df_for_clean.loc[is_acc_empty_dest & (withdraw_numeric != 0), 'หมายเลขบัญชีปลายทาง'] = df_for_clean['ประเภทรายการ']

    if 'ฝากเงิน' in df_for_clean.columns:
        dest_cols = ['ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง']
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
        df_cleaned['ยอดเงิน'], df_cleaned['_source_type'] = 0, 'UNKNOWN'
        
    df_cleaned['จำนวนครั้ง'] = 1
    df_cleaned['ยอดเงิน'] = df_cleaned['ยอดเงิน'].replace([np.inf, -np.inf], np.nan)
    df_cleaned_ready = df_cleaned.fillna('') 
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_original_copy.to_excel(writer, sheet_name='Original', index=False, header=False)
        ws_cleaned = writer.book.add_worksheet('Cleaned Data')
        
        g_fmt = writer.book.add_format({'font_color': 'green', 'num_format': '#,##0.00'})
        r_fmt = writer.book.add_format({'font_color': 'red', 'num_format': '#,##0.00'})
        d_fmt = writer.book.add_format({'num_format': 'General'})
        dt_fmt = writer.book.add_format({'num_format': 'dd/mm/yyyy'}) 
        t_fmt = writer.book.add_format({'num_format': '@'})

        for c, v in enumerate(new_columns): ws_cleaned.write(0, c, v, d_fmt)

        for r_num, r_data in df_cleaned_ready.iterrows():
            src = r_data['_source_type']
            for c_num, c_name in enumerate(new_columns):
                c_val = r_data[c_name]
                if c_name == 'ยอดเงิน':
                    fmt = g_fmt if src == 'DEPOSIT' else r_fmt
                    if c_val != '' and pd.notna(c_val): ws_cleaned.write_number(r_num + 1, c_num, c_val, fmt)
                    else: ws_cleaned.write_blank(r_num + 1, c_num, '', d_fmt)
                elif c_name == 'วันที่ทำรายการ' and c_val != '':
                    if isinstance(c_val, (pd.Timestamp, datetime)): ws_cleaned.write_datetime(r_num + 1, c_num, c_val, dt_fmt)
                    else: ws_cleaned.write(r_num + 1, c_num, c_val, d_fmt)
                elif c_name in ['หมายเลขบัญชีต้นทาง', 'หมายเลขบัญชีปลายทาง']:
                    ws_cleaned.write_string(r_num + 1, c_num, str(c_val), t_fmt)
                else: ws_cleaned.write(r_num + 1, c_num, c_val, d_fmt)
        ws_cleaned.autofit()
        
    return output.getvalue(), df_cleaned_ready, warn_msg

# ==========================================
# ส่วนประมวลผล KTB
# ==========================================
def process_ktb(excel_file, account_number, account_name):
    df_full_raw = pd.read_excel(excel_file, sheet_name=0, header=None)
    df_data_map = df_full_raw.copy()
    df_data_map.columns = df_data_map.iloc[0].astype(str).str.strip().str.replace(r'[\s\n-]', '', regex=True).str.lower()
    df_data_map = df_data_map[1:].reset_index(drop=True)
    
    expected_headers = ['วันที่', 'เวลา', 'รายการ', 'สถานที่', 'จำนวนเงิน']
    missing, renamed = fix_and_validate_headers(df_data_map, expected_headers)
    
    if missing:
        raise ValueError(f"⚠️ รูปแบบหัวตารางไม่ถูกต้อง! \nระบบต้องการคอลัมน์: {', '.join(missing)} \nกรุณาแก้ไขชื่อหัวตารางในไฟล์ Excel ให้ตรงตามรูปแบบก่อนทำรายการ")
        
    warn_msg = "ระบบได้ทำการปรับแก้หัวตารางอัตโนมัติ:\n" + " | ".join(renamed) if renamed else ""

    new_columns = ['วันที่ทำรายการ', 'เวลาที่ทำรายการ', 'ประเภทรายการ', 'ช่องทาง', 'ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง', 'ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง', 'ยอดเงิน', 'จำนวนครั้ง']
    df_cleaned = pd.DataFrame(index=df_data_map.index, columns=new_columns)

    def force_clean_text(val): return '' if str(val).strip().lower() in ['nan', 'none', 'nat', ''] else str(val).strip()
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

    return output.getvalue(), df_cleaned, warn_msg

# ==========================================
# ส่วนประมวลผล TTB
# ==========================================
def process_ttb(excel_file):
    raw_df_original = pd.read_excel(excel_file)
    raw_df = pd.read_excel(excel_file, dtype=str, keep_default_na=False)

    expected_headers = ['DATE', 'TIME', 'TYPE', 'CHANNEL', 'FROM BANK CODE', 'FROM ACCOUNT NO', 'TO BANK CODE', 'TO ACCOUNT NO', 'DEPOSIT', 'WITHDRAWAL']
    missing, renamed = fix_and_validate_headers(raw_df, expected_headers)
    
    if missing:
        raise ValueError(f"⚠️ รูปแบบหัวตารางไม่ถูกต้อง! \nระบบต้องการคอลัมน์: {', '.join(missing)} \nกรุณาแก้ไขชื่อหัวตารางในไฟล์ Excel ให้ตรงตามรูปแบบก่อนทำรายการ")
        
    warn_msg = "ระบบได้ทำการปรับแก้หัวตารางอัตโนมัติ:\n" + " | ".join(renamed) if renamed else ""

    bank_mapping = {'001': 'BOT', '002': 'BBL', '004': 'KBANK', '006': 'KTB', '011': 'TTB', '014': 'SCB', '020': 'SCBT', '022': 'CIMBT', '024': 'UOB', '025': 'BAY', '030': 'GSB', '033': 'GHB', '034': 'BAAC', '035': 'EXIM', '065': 'TBANK', '066': 'IBANK', '067': 'TISCO', '069': 'KKP', '070': 'ICBCT', '071': 'TCRB', '073': 'LHBA', '098': 'SME'}
    
    def map_bank(code):
        if not code or str(code).strip() in ['nan', '']: return ""
        code_str = str(code).strip().replace('.0', '').zfill(3)
        return bank_mapping.get(code_str, code_str)

    def find_col_flexible(df, target_name):
        target_norm = target_name.replace(' ', '').lower()
        for col in df.columns:
            if str(col).replace(' ', '').replace('\n', '').replace('-', '').lower() == target_norm:
                return col
        return None

    from_name_col = find_col_flexible(raw_df, 'fromaccountname')
    to_name_col = find_col_flexible(raw_df, 'toaccountname')

    clean_df = pd.DataFrame()
    clean_df['วันที่ทำรายการ'] = raw_df.get('DATE', pd.Series(dtype=str)).apply(convert_buddhist_year_string)
    clean_df['เวลาที่ทำรายการ'] = raw_df.get('TIME', pd.Series(dtype=str)).astype(str).replace('nan', '')
    clean_df['ประเภทรายการ'] = raw_df.get('TYPE', pd.Series(dtype=str)).astype(str).replace('nan', '')
    clean_df['ช่องทาง'] = raw_df.get('CHANNEL', pd.Series(dtype=str)).astype(str).replace('nan', '')
    
    clean_df['ชื่อธนาคารต้นทาง'] = raw_df.get('FROM BANK CODE', pd.Series(dtype=str)).apply(map_bank)
    clean_df['หมายเลขบัญชีต้นทาง'] = raw_df.get('FROM ACCOUNT NO', pd.Series(dtype=str)).astype(str).replace('nan', '')
    
    clean_df['ชื่อบัญชีต้นทาง'] = raw_df[from_name_col].astype(str).replace('nan', '') if from_name_col else ""
    
    clean_df['ชื่อธนาคารปลายทาง'] = raw_df.get('TO BANK CODE', pd.Series(dtype=str)).apply(map_bank)
    clean_df['หมายเลขบัญชีปลายทาง'] = raw_df.get('TO ACCOUNT NO', pd.Series(dtype=str)).astype(str).replace('nan', '')
    
    clean_df['ชื่อบัญชีปลายทาง'] = raw_df[to_name_col].astype(str).replace('nan', '') if to_name_col else ""

    clean_df['หมายเลขบัญชีต้นทาง'] = clean_df['หมายเลขบัญชีต้นทาง'].replace('', pd.NA).fillna(clean_df['ประเภทรายการ'])
    clean_df['หมายเลขบัญชีปลายทาง'] = clean_df['หมายเลขบัญชีปลายทาง'].replace('', pd.NA).fillna(clean_df['ประเภทรายการ'])
    clean_df['ยอดเงิน'], clean_df['จำนวนครั้ง'] = 0.0, 1
    clean_df['_DEPOSIT'] = raw_df.get('DEPOSIT', pd.Series([None]*len(raw_df)))
    clean_df['_WITHDRAWAL'] = raw_df.get('WITHDRAWAL', pd.Series([None]*len(raw_df)))
    
    clean_df['_sort_date'] = pd.to_datetime(clean_df['วันที่ทำรายการ'], format='%d/%m/%Y', errors='coerce')
    clean_df['_sort_time'] = clean_df['เวลาที่ทำรายการ'].astype(str).str.strip()
    clean_df.sort_values(by=['_sort_date', '_sort_time'], inplace=True, na_position='first')

    def is_val(val): return False if pd.isna(val) or str(val).strip() in ['-', '0', '0.0', 'nan', ''] else True

    clean_df['_source_type'] = 'UNKNOWN'
    for idx, row in clean_df.iterrows():
        dep, wit = row['_DEPOSIT'], row['_WITHDRAWAL']
        if is_val(dep):
            clean_df.at[idx, '_source_type'] = 'DEPOSIT'
            try: clean_df.at[idx, 'ยอดเงิน'] = float(str(dep).replace(',', ''))
            except: clean_df.at[idx, 'ยอดเงิน'] = str(dep)
        elif is_val(wit):
            clean_df.at[idx, '_source_type'] = 'WITHDRAWAL'
            try: clean_df.at[idx, 'ยอดเงิน'] = float(str(wit).replace(',', ''))
            except: clean_df.at[idx, 'ยอดเงิน'] = str(wit)

    new_columns = ['วันที่ทำรายการ', 'เวลาที่ทำรายการ', 'ประเภทรายการ', 'ช่องทาง', 'ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง', 'ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง', 'ยอดเงิน', 'จำนวนครั้ง']
    clean_df = clean_df.reindex(columns=new_columns + ['_source_type'])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        raw_df_original.to_excel(writer, sheet_name='Sheet1_RawData', index=False)
        ws_cleaned = writer.book.add_worksheet('Sheet2_Cleaned Data')
        
        g_fmt = writer.book.add_format({'font_color': 'green', 'num_format': '#,##0.00'})
        r_fmt = writer.book.add_format({'font_color': 'red', 'num_format': '#,##0.00'})
        d_fmt = writer.book.add_format({'num_format': 'General'})
        t_fmt = writer.book.add_format({'num_format': '@'})

        for c, v in enumerate(new_columns): ws_cleaned.write(0, c, v, d_fmt)

        for r_num, r_data in clean_df.iterrows():
            src = r_data['_source_type']
            for c_num, c_name in enumerate(new_columns):
                c_val = r_data[c_name]
                if c_name == 'ยอดเงิน':
                    fmt = g_fmt if src == 'DEPOSIT' else r_fmt
                    if c_val != '' and pd.notna(c_val): ws_cleaned.write_number(r_num + 1, c_num, c_val, fmt)
                    else: ws_cleaned.write_blank(r_num + 1, c_num, '', d_fmt)
                elif c_name in ['วันที่ทำรายการ', 'เวลาที่ทำรายการ', 'หมายเลขบัญชีต้นทาง', 'หมายเลขบัญชีปลายทาง']:
                    ws_cleaned.write_string(r_num + 1, c_num, str(c_val), t_fmt)
                else:
                    ws_cleaned.write_string(r_num + 1, c_num, str(c_val), d_fmt)
        ws_cleaned.autofit()
        
    return output.getvalue(), clean_df, warn_msg

# ==========================================
# ส่วนประมวลผล GSB
# ==========================================
def process_gsb(excel_file):
    df_temp = pd.read_excel(excel_file, header=None, nrows=15)
    header_row_idx = 0
    for i, row in df_temp.iterrows():
        if row.astype(str).str.contains('วันที่ทำรายการ|รหัสรายการ|จำนวนเงิน', case=False, na=False).any():
            header_row_idx = i
            break

    excel_file.seek(0)
    df_orig = pd.read_excel(excel_file, header=header_row_idx, dtype=str)
    
    excel_file.seek(0)
    df_orig_copy = pd.read_excel(excel_file, sheet_name=0, header=None)

    df_orig.columns = [str(c).replace('\n', ' ').strip() for c in df_orig.columns]

    expected_headers = ['วันที่ทำรายการ', 'เวลาที่ทำรายการ', 'ประเภทรายการ', 'ช่องทาง', 'ชื่อธนาคารต้นทาง', 'เลขที่บัญชีต้นทาง', 'ชื่อบัญชีต้นทาง', 'ชื่อธนาคารปลายทาง', 'เลขที่บัญชีปลายทาง', 'ชื่อบัญชีปลายทาง', 'รหัสรายการ', 'จำนวนเงิน']
    missing, renamed = fix_and_validate_headers(df_orig, expected_headers)
    
    if missing:
        raise ValueError(f"⚠️ รูปแบบหัวตารางไม่ถูกต้อง! \nระบบต้องการคอลัมน์: {', '.join(missing)} \nกรุณาแก้ไขชื่อหัวตารางในไฟล์ Excel ให้ตรงตามรูปแบบก่อนทำรายการ")
        
    warn_msg = "ระบบได้ทำการปรับแก้หัวตารางอัตโนมัติ:\n" + " | ".join(renamed) if renamed else ""

    def convert_thai_date(date_val):
        if pd.isna(date_val) or str(date_val).strip() in ["", "nan"]: return date_val
        d_str = str(date_val).strip()
        thai_months = {"ม.ค.": "01", "ก.พ.": "02", "มี.ค.": "03", "เม.ย.": "04", "พ.ค.": "05", "มิ.ย.": "06", "ก.ค.": "07", "ส.ค.": "08", "ก.ย.": "09", "ต.ค.": "10", "พ.ย.": "11", "ธ.ค.": "12"}
        for th, en in thai_months.items():
            if th in d_str: d_str = d_str.replace(th, en); break
        parts = d_str.split()
        if len(parts) >= 3:
            try:
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                if year > 2500: year -= 543
                return f"{day:02d}/{month:02d}/{year}"
            except: pass
        return d_str

    def map_gsb_bank(bank_name):
        if pd.isna(bank_name) or str(bank_name).strip().lower() == "nan": return ""
        b = str(bank_name).strip().upper()
        if 'KBNK' in b or 'KASIKORN' in b or 'กสิกร' in b: return 'KBANK'
        if 'SCB' in b or 'SIAM COM' in b or 'ไทยพาณิชย์' in b: return 'SCB'
        if 'BBL' in b or 'BANGKOK' in b or 'กรุงเทพ' in b: return 'BBL'
        if 'KTB' in b or 'KRUNG THAI' in b or 'กรุงไทย' in b: return 'KTB'
        if 'BAY' in b or 'KRUNGSRI' in b or 'กรุงศรี' in b: return 'BAY'
        if 'TTB' in b or 'TMB' in b or 'THANACHART' in b or 'ทหารไทย' in b: return 'TTB'
        if 'GSB' in b or 'GOVERNMENT SAVING' in b or 'ออมสิน' in b: return 'GSB'
        if 'BAAC' in b or 'ธ.ก.ส.' in b or 'เพื่อการเกษตร' in b: return 'BAAC'
        if 'UOB' in b or 'ยูโอบี' in b: return 'UOB'
        return b

    def get_col(name):
        return df_orig[name] if name in df_orig.columns else pd.Series([""] * len(df_orig))

    df_new = pd.DataFrame()
    df_new['วันที่ทำรายการ'] = get_col('วันที่ทำรายการ').apply(convert_thai_date)
    df_new['วันที่ทำรายการ'] = pd.to_datetime(df_new['วันที่ทำรายการ'], format='%d/%m/%Y', errors='coerce')
    
    df_new['เวลาที่ทำรายการ'] = get_col('เวลาที่ทำรายการ').fillna('').astype(str).replace('nan', '')
    df_new['ประเภทรายการ'] = get_col('ประเภทรายการ').fillna('').astype(str).replace('nan', '')
    df_new['ช่องทาง'] = get_col('ช่องทาง').fillna('').astype(str).replace('nan', '')
    
    df_new['ชื่อธนาคารต้นทาง'] = get_col('ชื่อธนาคารต้นทาง').apply(map_gsb_bank)
    df_new['หมายเลขบัญชีต้นทาง'] = get_col('เลขที่บัญชีต้นทาง').apply(lambda x: str(x).strip().replace('.0','') if pd.notna(x) and str(x).lower() != 'nan' else '')
    df_new['ชื่อบัญชีต้นทาง'] = get_col('ชื่อบัญชีต้นทาง').apply(lambda x: str(x).strip() if pd.notna(x) and str(x).lower() != 'nan' else '')
    
    df_new['ชื่อธนาคารปลายทาง'] = get_col('ชื่อธนาคารปลายทาง').apply(map_gsb_bank)
    df_new['หมายเลขบัญชีปลายทาง'] = get_col('เลขที่บัญชีปลายทาง').apply(lambda x: str(x).strip().replace('.0','') if pd.notna(x) and str(x).lower() != 'nan' else '')
    df_new['ชื่อบัญชีปลายทาง'] = get_col('ชื่อบัญชีปลายทาง').apply(lambda x: str(x).strip() if pd.notna(x) and str(x).lower() != 'nan' else '')
    
    df_new['ยอดเงิน'] = pd.to_numeric(get_col('จำนวนเงิน').astype(str).replace({',': ''}, regex=True), errors='coerce').fillna(0)
    df_new['จำนวนครั้ง'] = 1

    all_acc_no = pd.concat([df_new[df_new['หมายเลขบัญชีต้นทาง'] != '']['หมายเลขบัญชีต้นทาง'], df_new[df_new['หมายเลขบัญชีปลายทาง'] != '']['หมายเลขบัญชีปลายทาง']])
    top_acc_no = all_acc_no.mode()[0] if not all_acc_no.empty else ""

    all_acc_name = pd.concat([df_new[df_new['ชื่อบัญชีต้นทาง'] != '']['ชื่อบัญชีต้นทาง'], df_new[df_new['ชื่อบัญชีปลายทาง'] != '']['ชื่อบัญชีปลายทาง']])
    top_acc_name = all_acc_name.mode()[0] if not all_acc_name.empty else ""

    dep_list = ['SDCA', 'BASD', 'ORSDC', 'ATSDC']
    wtd_list = ['ATSWC', 'ATSFE', 'MASWC', 'MASFE', 'IIPS', 'PSLSSWP', 'SWATMFE', 'SWCA']

    for idx in df_new.index:
        raw_code = str(get_col('รหัสรายการ').iloc[idx]).strip().upper() 
        txn_type = str(df_new.at[idx, 'ประเภทรายการ']).strip() 
        
        acc_from = df_new.at[idx, 'หมายเลขบัญชีต้นทาง']
        acc_to = df_new.at[idx, 'หมายเลขบัญชีปลายทาง']
        
        is_empty_from = (acc_from == '')
        is_empty_to = (acc_to == '')
        
        if raw_code in dep_list:
            if is_empty_from or is_empty_to:
                df_new.at[idx, 'หมายเลขบัญชีต้นทาง'] = txn_type
                df_new.at[idx, 'ชื่อธนาคารปลายทาง'] = 'GSB'
                df_new.at[idx, 'หมายเลขบัญชีปลายทาง'] = top_acc_no
                df_new.at[idx, 'ชื่อบัญชีปลายทาง'] = top_acc_name
                
        elif raw_code in wtd_list:
            if is_empty_from or is_empty_to:
                df_new.at[idx, 'หมายเลขบัญชีปลายทาง'] = txn_type
                df_new.at[idx, 'ชื่อธนาคารต้นทาง'] = 'GSB'
                df_new.at[idx, 'หมายเลขบัญชีต้นทาง'] = top_acc_no
                df_new.at[idx, 'ชื่อบัญชีต้นทาง'] = top_acc_name

    df_new['วันที่ทำรายการ'] = df_new['วันที่ทำรายการ'].astype(object).where(pd.notna(df_new['วันที่ทำรายการ']), '')

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_orig_copy.to_excel(writer, sheet_name='Sheet1 (Original)', index=False, header=False)
        ws_cleaned = writer.book.add_worksheet('Sheet2 (Cleaned Data)')
        
        g_fmt = writer.book.add_format({'font_color': 'green', 'num_format': '#,##0.00'})
        r_fmt = writer.book.add_format({'font_color': 'red', 'num_format': '#,##0.00'})
        d_fmt = writer.book.add_format({'num_format': 'General'})
        dt_fmt = writer.book.add_format({'num_format': 'dd/mm/yyyy'}) 
        t_fmt = writer.book.add_format({'num_format': '@'})

        new_cols = ['วันที่ทำรายการ', 'เวลาที่ทำรายการ', 'ประเภทรายการ', 'ช่องทาง', 'ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง', 'ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง', 'ยอดเงิน', 'จำนวนครั้ง']
        
        for c, v in enumerate(new_cols): ws_cleaned.write(0, c, v, d_fmt)

        top_acc_compare = str(top_acc_no).lstrip('0')

        for r_num, r_data in df_new.iterrows():
            acc_from = str(r_data['หมายเลขบัญชีต้นทาง']).strip()
            acc_to = str(r_data['หมายเลขบัญชีปลายทาง']).strip()
            
            fmt_to_use = d_fmt
            if acc_from.lstrip('0') == top_acc_compare:
                fmt_to_use = r_fmt
            elif acc_to.lstrip('0') == top_acc_compare:
                fmt_to_use = g_fmt

            for c_num, c_name in enumerate(new_cols):
                c_val = r_data[c_name]
                if c_name == 'ยอดเงิน':
                    if c_val != '' and pd.notna(c_val): ws_cleaned.write_number(r_num + 1, c_num, c_val, fmt_to_use)
                    else: ws_cleaned.write_blank(r_num + 1, c_num, '', d_fmt)
                elif c_name == 'วันที่ทำรายการ' and c_val != '':
                    if isinstance(c_val, (pd.Timestamp, datetime)): ws_cleaned.write_datetime(r_num + 1, c_num, c_val, dt_fmt)
                    else: ws_cleaned.write(r_num + 1, c_num, c_val, d_fmt)
                elif c_name in ['หมายเลขบัญชีต้นทาง', 'หมายเลขบัญชีปลายทาง']:
                    ws_cleaned.write_string(r_num + 1, c_num, str(c_val), t_fmt)
                else:
                    ws_cleaned.write_string(r_num + 1, c_num, str(c_val), d_fmt)
        ws_cleaned.autofit()
        
    return output.getvalue(), df_new, warn_msg

# ==========================================
# ส่วนประมวลผล PRASAN (ระบบประสาน)
# ==========================================
def process_prasan(excel_file):
    df_for_clean = pd.read_excel(excel_file, sheet_name=0, header=0)
    df_original_copy = pd.read_excel(excel_file, sheet_name=0, header=None)

    expected_headers = ['txdate', 'txtime', 'frombankcode', 'fromaccountno', 'fromaccountname', 
                        'tobankcode', 'toaccountno', 'toaccountname', 'txtype', 'txchannel', 
                        'deposit', 'withdrawal', 'bankcode', 'accountno', 'accountname']
    
    df_for_clean.columns = df_for_clean.columns.astype(str).str.lower().str.strip()
    
    missing, renamed = fix_and_validate_headers(df_for_clean, expected_headers)
    warn_msg = "ระบบได้ทำการปรับแก้หัวตารางอัตโนมัติ:\n" + " | ".join(renamed) if renamed else ""

    BANK_CODE_MAP = {
        '002': 'BBL', '004': 'KBANK', '006': 'KTB', '011': 'TTB', '014': 'SCB',
        '017': 'CITI', '020': 'SCB', '022': 'CIMB', '024': 'TISCO', '025': 'UOB',
        '030': 'GSB', '033': 'GHB', '034': 'BAAC', '052': 'ISBT', '065': 'Krungsri',
        '066': 'LHBank', '067': 'KKP', '069': 'ICBC', '071': 'TCRB', '073': 'EXIM',
        'EBANK': 'E-CHANNEL', 'OTHER': 'OTHER'
    }
    FULL_BANK_CODES = {k.lstrip('0'): v for k, v in BANK_CODE_MAP.items() if k.isdigit()}
    FULL_BANK_CODES.update(BANK_CODE_MAP)

    def clean_string_or_nan(series, is_account_no=False, is_bank_code=False):
        series_str = series.astype(str).str.strip().str.upper()
        series_str = series_str.replace('NAN', '', regex=False).replace('NONE', '', regex=False)
        series_str = series_str.mask(series.isna(), '')
        if is_account_no or is_bank_code:
            series_str = series_str.str.replace(r'\.0$', '', regex=True)
        return series_str

    def map_bank_codes(code_series):
        def mapper(code):
            code = str(code).strip().upper()
            if code in FULL_BANK_CODES: return FULL_BANK_CODES[code]
            elif code.lstrip('0') in FULL_BANK_CODES: return FULL_BANK_CODES[code.lstrip('0')]
            elif code == '': return ''
            return code 
        return code_series.apply(mapper)

    new_columns = ['วันที่ทำรายการ', 'เวลาที่ทำรายการ', 'ประเภทรายการ', 'ช่องทาง', 'ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง', 'ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง', 'ยอดเงิน', 'จำนวนครั้ง']
    df_cleaned = pd.DataFrame(columns=new_columns)

    mapping = {
        'txdate': 'วันที่ทำรายการ', 'txtime': 'เวลาที่ทำรายการ',
        'frombankcode': 'ชื่อธนาคารต้นทาง', 'fromaccountno': 'หมายเลขบัญชีต้นทาง',
        'fromaccountname': 'ชื่อบัญชีต้นทาง', 'tobankcode': 'ชื่อธนาคารปลายทาง',
        'toaccountno': 'หมายเลขบัญชีปลายทาง', 'toaccountname': 'ชื่อบัญชีปลายทาง',
        'txtype': 'ประเภทรายการ', 'txchannel': 'ช่องทาง'
    }

    for src, dest in mapping.items():
        if src in df_for_clean.columns:
            if dest == 'วันที่ทำรายการ':
                df_for_clean['txdate'] = df_for_clean['txdate'].apply(convert_buddhist_year_string)
                df_cleaned[dest] = pd.to_datetime(df_for_clean['txdate'], errors='coerce', dayfirst=True)
            elif dest in ['หมายเลขบัญชีต้นทาง', 'หมายเลขบัญชีปลายทาง']:
                df_cleaned[dest] = clean_string_or_nan(df_for_clean[src], is_account_no=True)
            elif dest in ['ชื่อธนาคารต้นทาง', 'ชื่อธนาคารปลายทาง']:
                cleaned_codes = clean_string_or_nan(df_for_clean[src], is_bank_code=True)
                df_cleaned[dest] = map_bank_codes(cleaned_codes)
            elif dest in ['ชื่อบัญชีต้นทาง', 'ชื่อบัญชีปลายทาง', 'ประเภทรายการ', 'ช่องทาง']:
                df_cleaned[dest] = clean_string_or_nan(df_for_clean[src])
            elif dest == 'เวลาที่ทำรายการ':
                df_cleaned[dest] = df_for_clean[src].fillna('').astype(str).str.strip()
            else:
                df_cleaned[dest] = df_for_clean[src]
        else:
            df_cleaned[dest] = ''

    dest_cols = ['ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง']
    if all(col in df_for_clean.columns for col in ['deposit', 'bankcode', 'accountno', 'accountname']):
        is_dest_empty = df_cleaned[dest_cols].apply(lambda col: col == '').all(axis=1)
        deposit_numeric = pd.to_numeric(df_for_clean['deposit'], errors='coerce').fillna(0)
        mask_fill_dest_owner = is_dest_empty & (deposit_numeric != 0)
        
        bank_codes_to_fill = clean_string_or_nan(df_for_clean.loc[mask_fill_dest_owner, 'bankcode'], is_bank_code=True)
        df_cleaned.loc[mask_fill_dest_owner, 'ชื่อธนาคารปลายทาง'] = map_bank_codes(bank_codes_to_fill)
        df_cleaned.loc[mask_fill_dest_owner, 'หมายเลขบัญชีปลายทาง'] = clean_string_or_nan(df_for_clean.loc[mask_fill_dest_owner, 'accountno'], is_account_no=True)
        df_cleaned.loc[mask_fill_dest_owner, 'ชื่อบัญชีปลายทาง'] = clean_string_or_nan(df_for_clean.loc[mask_fill_dest_owner, 'accountname'])

    source_cols = ['ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง']
    if all(col in df_for_clean.columns for col in ['withdrawal', 'bankcode', 'accountno', 'accountname']):
        is_source_empty = df_cleaned[source_cols].apply(lambda col: col == '').all(axis=1)
        withdrawal_numeric = pd.to_numeric(df_for_clean['withdrawal'], errors='coerce').fillna(0)
        mask_fill_source_owner = is_source_empty & (withdrawal_numeric != 0)

        bank_codes_to_fill = clean_string_or_nan(df_for_clean.loc[mask_fill_source_owner, 'bankcode'], is_bank_code=True)
        df_cleaned.loc[mask_fill_source_owner, 'ชื่อธนาคารต้นทาง'] = map_bank_codes(bank_codes_to_fill)
        df_cleaned.loc[mask_fill_source_owner, 'หมายเลขบัญชีต้นทาง'] = clean_string_or_nan(df_for_clean.loc[mask_fill_source_owner, 'accountno'], is_account_no=True)
        df_cleaned.loc[mask_fill_source_owner, 'ชื่อบัญชีต้นทาง'] = clean_string_or_nan(df_for_clean.loc[mask_fill_source_owner, 'accountname'])

    if 'deposit' in df_for_clean.columns and 'txtype' in df_for_clean.columns:
        is_acc_empty = (df_cleaned['หมายเลขบัญชีต้นทาง'] == '')
        deposit_numeric = pd.to_numeric(df_for_clean['deposit'], errors='coerce').fillna(0)
        mask_fill_type = is_acc_empty & (deposit_numeric != 0)
        df_cleaned.loc[mask_fill_type, 'หมายเลขบัญชีต้นทาง'] = clean_string_or_nan(df_for_clean.loc[mask_fill_type, 'txtype'])

    if 'withdrawal' in df_for_clean.columns and 'txtype' in df_for_clean.columns:
        is_acc_empty_dest = (df_cleaned['หมายเลขบัญชีปลายทาง'] == '')
        withdrawal_numeric = pd.to_numeric(df_for_clean['withdrawal'], errors='coerce').fillna(0)
        mask_fill_type_dest = is_acc_empty_dest & (withdrawal_numeric != 0)
        df_cleaned.loc[mask_fill_type_dest, 'หมายเลขบัญชีปลายทาง'] = clean_string_or_nan(df_for_clean.loc[mask_fill_type_dest, 'txtype'])

    source_column = '_source_type'
    if 'deposit' in df_for_clean.columns and 'withdrawal' in df_for_clean.columns:
        deposit = pd.to_numeric(df_for_clean['deposit'], errors='coerce').fillna(0)
        withdrawal = pd.to_numeric(df_for_clean['withdrawal'], errors='coerce').fillna(0)
        df_cleaned['ยอดเงิน'] = np.where(deposit != 0, deposit, withdrawal)
        df_cleaned[source_column] = np.where(deposit != 0, 'DEPOSIT', 'WITHDRAWAL')
    else:
        df_cleaned['ยอดเงิน'] = 0
        df_cleaned[source_column] = 'UNKNOWN'

    df_cleaned['จำนวนครั้ง'] = 1
    df_cleaned['ยอดเงิน'] = df_cleaned['ยอดเงิน'].replace([np.inf, -np.inf], np.nan)
    df_cleaned['วันที่ทำรายการ'] = df_cleaned['วันที่ทำรายการ'].astype(object).where(pd.notna(df_cleaned['วันที่ทำรายการ']), '')
    
    df_cleaned_ready = df_cleaned.copy()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_original_copy.to_excel(writer, sheet_name='Sheet1 (Original)', index=False, header=False)
        ws_cleaned = writer.book.add_worksheet('Sheet2 (Cleaned Data)')
        
        g_fmt = writer.book.add_format({'font_color': 'green', 'num_format': '#,##0.00'})
        r_fmt = writer.book.add_format({'font_color': 'red', 'num_format': '#,##0.00'})
        d_fmt = writer.book.add_format({'num_format': 'General'})
        dt_fmt = writer.book.add_format({'num_format': 'dd/mm/yyyy'}) 
        t_fmt = writer.book.add_format({'num_format': '@'})

        for c, v in enumerate(new_columns): ws_cleaned.write(0, c, v, d_fmt)

        for r_num, r_data in df_cleaned_ready.iterrows():
            src = r_data[source_column]
            for c_num, c_name in enumerate(new_columns):
                c_val = r_data[c_name]
                if c_name == 'ยอดเงิน':
                    fmt = g_fmt if src == 'DEPOSIT' else r_fmt
                    if pd.notna(c_val) and c_val != '': ws_cleaned.write_number(r_num + 1, c_num, c_val, fmt)
                    else: ws_cleaned.write_blank(r_num + 1, c_num, '', d_fmt)
                elif c_name == 'วันที่ทำรายการ' and c_val != '':
                    if isinstance(c_val, (pd.Timestamp, datetime)): ws_cleaned.write_datetime(r_num + 1, c_num, c_val, dt_fmt)
                    else: ws_cleaned.write(r_num + 1, c_num, c_val, d_fmt)
                elif c_name in ['หมายเลขบัญชีต้นทาง', 'หมายเลขบัญชีปลายทาง']:
                    ws_cleaned.write_string(r_num + 1, c_num, str(c_val), t_fmt)
                else:
                    ws_cleaned.write_string(r_num + 1, c_num, str(c_val), d_fmt)
        ws_cleaned.autofit()
        
    return output.getvalue(), df_cleaned_ready, warn_msg

# ==========================================
# ส่วนประมวลผล SCB
# ==========================================
def map_scb_bank(bank_name):
    if pd.isna(bank_name) or str(bank_name).strip() == "": return ""
    b = str(bank_name).strip().upper()
    if 'KBNK' in b or 'KASIKORN' in b or 'กสิกร' in b: return 'KBANK'
    if 'SCB' in b or 'SIAM COM' in b or 'ไทยพาณิชย์' in b: return 'SCB'
    if 'BBL' in b or 'BANGKOK' in b or 'กรุงเทพ' in b: return 'BBL'
    if 'KTB' in b or 'KRUNG THAI' in b or 'กรุงไทย' in b: return 'KTB'
    if 'BAY' in b or 'KRUNGSRI' in b or 'กรุงศรี' in b: return 'BAY'
    if 'TTB' in b or 'TMB' in b or 'THANACHART' in b or 'ทหารไทย' in b: return 'TTB'
    if 'GSB' in b or 'ออมสิน' in b: return 'GSB'
    return b

def clean_description_c(desc):
    desc = str(desc).strip()
    m1 = re.search(r'(?:รับโอนจาก|รับเงินจาก|คืนเงินโอนไป)\s+(\w+)\s+(\S+)\s+(.*)', desc)
    if m1: return map_scb_bank(m1.group(1)), str(m1.group(2)).strip(), m1.group(3).strip()
    m2 = re.search(r'Transfer from\s+(\w+)\s+(\S+)\s+(.*)', desc, re.IGNORECASE)
    if m2: return map_scb_bank(m2.group(1)), str(m2.group(2)).strip(), m2.group(3).strip()
    m3 = re.search(r'PromptPay\s+(\S+)\s+(.*)', desc, re.IGNORECASE)
    if m3: return "PromptPay", str(m3.group(1)).strip(), m3.group(2).strip()
    m4 = re.search(r'\((.*?)\)\s*/(\S+)', desc)
    if m4: return map_scb_bank(m4.group(1)), str(m4.group(2)).strip(), ""
    return "", desc, ""

def clean_description_d(desc):
    desc = str(desc).strip()
    m1 = re.search(r'โอนไป\s+(\w+)\s+(\S+)\s+(.*)', desc)
    if m1: return map_scb_bank(m1.group(1)), str(m1.group(2)).strip(), m1.group(3).strip()
    m2 = re.search(r'Transfer to\s+(\w+)\s+(\S+)\s+(.*)', desc, re.IGNORECASE)
    if m2: return map_scb_bank(m2.group(1)), str(m2.group(2)).strip(), m2.group(3).strip()
    m3 = re.search(r'PromptPay\s+(\S+)\s+(.*)', desc, re.IGNORECASE)
    if m3: return "PromptPay", str(m3.group(1)).strip(), m3.group(2).strip()
    return "", desc, ""

def process_scb(excel_file, filename, main_acc_num, main_acc_name):
    is_csv = filename.lower().endswith('.csv')
    
    excel_file.seek(0)
    if is_csv:
        try: raw_df = pd.read_csv(excel_file, header=None, dtype=str)
        except UnicodeDecodeError:
            excel_file.seek(0)
            raw_df = pd.read_csv(excel_file, header=None, encoding='tis-620', dtype=str)
    else:
        raw_df = pd.read_excel(excel_file, header=None, dtype=str)

    header_idx = None
    fmt_type = 0
    
    for i, row in raw_df.iterrows():
        row_str = " ".join([str(val).strip().lower() for val in row.values])
        if 'tran_date' in row_str and 'dr_cr_ind' in row_str:
            header_idx = i; fmt_type = 1; break
        elif 'date' in row_str and 'debit' in row_str and 'credit' in row_str:
            header_idx = i; fmt_type = 2; break
            
    if header_idx is None:
        raise ValueError("⚠️ ไม่พบหัวตารางที่รองรับ (โปรดตรวจสอบว่าไฟล์มีคำว่า TRAN_DATE หรือ Date / Debit / Credit อย่างใดอย่างหนึ่ง)")

    df = raw_df.iloc[header_idx+1:].copy()
    df.columns = [str(c).strip() for c in raw_df.iloc[header_idx].values]
    df = df.loc[:, df.columns.notna()]

    has_acc_col = 'ACCT_NO' in df.columns and not df['ACCT_NO'].dropna().empty
    has_name_col = 'ACCT_NAME' in df.columns and not df['ACCT_NAME'].dropna().empty

    if has_acc_col and has_name_col:
        f_acc = str(df['ACCT_NO'].dropna().iloc[0]).strip()
        f_name = str(df['ACCT_NAME'].dropna().iloc[0]).strip()
        f_bank = "SCB"
    else:
        if not main_acc_num:
            raise ValueError("⚠️ ไฟล์นี้ไม่มีข้อมูลเลขบัญชีหลัก กรุณาระบุ 'หมายเลขบัญชีหลัก' ในขั้นตอนที่ 1 ก่อนทำการอัปโหลดไฟล์")
        f_bank = "SCB"
        f_acc = str(main_acc_num).strip()
        f_name = str(main_acc_name).strip() if main_acc_name else ""

    int_df = pd.DataFrame()

    if fmt_type == 1:
        int_df['TRAN_DATE'] = df['TRAN_DATE'].apply(convert_buddhist_year_string)
        int_df['TRAN_TIME'] = df['TRAN_TIME']
        int_df['ACTIVITIE'] = df.get('ACTIVITIE', pd.Series([""] * len(df)))
        int_df['CHANNEL'] = df.get('CHANNEL', pd.Series([""] * len(df)))
        int_df['DR_CR_IND'] = df['DR_CR_IND']
        int_df['TRAN_AMT'] = df['TRAN_AMT']
        int_df['DESCRIPTION'] = df['DESCRIPTION']
        
    elif fmt_type == 2:
        def extract_amt_ind(row):
            d_val = pd.to_numeric(str(row.get('Debit', 0)).replace(',', ''), errors='coerce')
            c_val = pd.to_numeric(str(row.get('Credit', 0)).replace(',', ''), errors='coerce')
            d_val = d_val if pd.notna(d_val) else 0
            c_val = c_val if pd.notna(c_val) else 0
            if d_val > 0: return 'D', d_val
            elif c_val > 0: return 'C', c_val
            return '', 0

        ind_amt_list = df.apply(extract_amt_ind, axis=1)
        int_df['TRAN_DATE'] = df['Date'].apply(convert_buddhist_year_string)
        int_df['TRAN_TIME'] = df['Time']
        int_df['ACTIVITIE'] = df['Code']
        int_df['CHANNEL'] = df['Channel']
        int_df['DR_CR_IND'] = [x[0] for x in ind_amt_list]
        int_df['TRAN_AMT'] = [x[1] for x in ind_amt_list]
        int_df['DESCRIPTION'] = df['Description']

    new_cols = ['วันที่ทำรายการ', 'เวลาที่ทำรายการ', 'ประเภทรายการ', 'ช่องทาง', 'ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง', 'ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง', 'ยอดเงิน', 'จำนวนครั้ง']
    
    combined_data = []
    for _, row in int_df.iterrows():
        ind = str(row['DR_CR_IND']).strip().upper()
        if not ind or ind == 'NAN': continue
        
        fmt_date = row['TRAN_DATE']
        try: sort_dt = pd.to_datetime(f"{fmt_date} {row['TRAN_TIME']}", format='%d/%m/%Y %H:%M:%S', errors='coerce')
        except: sort_dt = datetime.max

        common = [fmt_date, str(row['TRAN_TIME']).replace('nan',''), str(row['ACTIVITIE']).replace('nan',''), str(row['CHANNEL']).replace('nan','')]
        try: amt = float(str(row['TRAN_AMT']).replace(',', ''))
        except: amt = 0

        if ind == 'C': 
            b_src, a_src, n_src = clean_description_c(row['DESCRIPTION'])
            combined_data.append({
                'data': common + [b_src, a_src, n_src, f_bank, f_acc, f_name, amt, 1],
                'type': 'DEPOSIT', 'sort_val': sort_dt
            })
        elif ind == 'D': 
            b_dest, a_dest, n_dest = clean_description_d(row['DESCRIPTION'])
            combined_data.append({
                'data': common + [f_bank, f_acc, f_name, b_dest, a_dest, n_dest, amt, 1],
                'type': 'WITHDRAWAL', 'sort_val': sort_dt
            })

    res_all = pd.DataFrame([x['data'] for x in combined_data], columns=new_cols)
    res_all['_source_type'] = [x['type'] for x in combined_data]
    res_all['วันที่ทำรายการ'] = pd.to_datetime(res_all['วันที่ทำรายการ'], format='%d/%m/%Y', errors='coerce')
    res_all['วันที่ทำรายการ'] = res_all['วันที่ทำรายการ'].astype(object).where(pd.notna(res_all['วันที่ทำรายการ']), '')
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        raw_df.to_excel(writer, sheet_name='Sheet1 (Original)', index=False, header=False)
        ws_cleaned = writer.book.add_worksheet('Sheet2 (Cleaned Data)')
        
        g_fmt = writer.book.add_format({'font_color': 'green', 'num_format': '#,##0.00'})
        r_fmt = writer.book.add_format({'font_color': 'red', 'num_format': '#,##0.00'})
        d_fmt = writer.book.add_format({'num_format': 'General'})
        dt_fmt = writer.book.add_format({'num_format': 'dd/mm/yyyy'}) 
        t_fmt = writer.book.add_format({'num_format': '@'})

        for c, v in enumerate(new_cols): ws_cleaned.write(0, c, v, d_fmt)

        for r_num, r_data in res_all.iterrows():
            src = r_data['_source_type']
            for c_num, c_name in enumerate(new_cols):
                c_val = r_data[c_name]
                if c_name == 'ยอดเงิน':
                    fmt = g_fmt if src == 'DEPOSIT' else r_fmt
                    if c_val != '' and pd.notna(c_val): ws_cleaned.write_number(r_num + 1, c_num, c_val, fmt)
                    else: ws_cleaned.write_blank(r_num + 1, c_num, '', d_fmt)
                elif c_name == 'วันที่ทำรายการ' and c_val != '':
                    if isinstance(c_val, (pd.Timestamp, datetime)): ws_cleaned.write_datetime(r_num + 1, c_num, c_val, dt_fmt)
                    else: ws_cleaned.write(r_num + 1, c_num, c_val, d_fmt)
                elif c_name in ['หมายเลขบัญชีต้นทาง', 'หมายเลขบัญชีปลายทาง']:
                    ws_cleaned.write_string(r_num + 1, c_num, str(c_val), t_fmt)
                else:
                    ws_cleaned.write_string(r_num + 1, c_num, str(c_val), d_fmt)
        ws_cleaned.autofit()
        
    return output.getvalue(), res_all, ""

# ==========================================
# Main Controller (UI)
# ==========================================
def process_and_allow_download(excel_file, bank_name, filename, main_acc_num="", main_acc_name=""):
    st.write("---")
    st.subheader("3. การประมวลผล (Processing)")
    
    try:
        warn_msg = ""
        if "KBANK" in bank_name:  
            st.info("กำลังประมวลผลข้อมูลตามโครงสร้างของธนาคารกสิกรไทย (KBANK)...")
            processed_data, df_show, warn_msg = process_kbank(excel_file)
        elif "KTB" in bank_name:
            if not main_acc_num or not main_acc_name:
                st.warning("ระบบไม่สามารถประมวลผลได้ กรุณากรอก 'หมายเลขบัญชีหลัก' และ 'ชื่อบัญชีหลัก' ด้านบนให้ครบถ้วน")
                return
            st.info("กำลังประมวลผลข้อมูลตามโครงสร้างของธนาคารกรุงไทย (KTB)...")
            processed_data, df_show, warn_msg = process_ktb(excel_file, main_acc_num, main_acc_name)
        elif "SCB" in bank_name:
            st.info("กำลังประมวลผลข้อมูลตามโครงสร้างของธนาคารไทยพาณิชย์ (SCB)...")
            processed_data, df_show, warn_msg = process_scb(excel_file, filename, main_acc_num, main_acc_name)
        elif "TTB" in bank_name:
            st.info("กำลังประมวลผลข้อมูลตามโครงสร้างของธนาคารทหารไทยธนชาต (TTB)...")
            processed_data, df_show, warn_msg = process_ttb(excel_file)
        elif "BBL" in bank_name:
            st.info("กำลังประมวลผลข้อมูลตามโครงสร้างของธนาคารกรุงเทพ (BBL)...")
            processed_data, df_show, warn_msg = process_bbl(excel_file)
        elif "GSB" in bank_name:
            st.info("กำลังประมวลผลข้อมูลตามโครงสร้างของธนาคารออมสิน (GSB)...")
            processed_data, df_show, warn_msg = process_gsb(excel_file)
        elif "PRASAN" in bank_name:
            st.info("กำลังประมวลผลข้อมูลตามโครงสร้างของระบบประสาน (PRASAN)...")
            processed_data, df_show, warn_msg = process_prasan(excel_file)
        else:
            st.error("ไม่พบโครงสร้างการประมวลผลของธนาคารนี้")
            return

        if warn_msg:
            st.warning(warn_msg)

        st.write("ตัวอย่างข้อมูลที่ประมวลผลแล้ว (5 แถวแรก):")
        display_df = df_show.drop(columns=['_source_type']) if '_source_type' in df_show.columns else df_show
        st.dataframe(display_df.head())

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = "PRASAN" if "PRASAN" in bank_name else bank_name.split()[0]
        
        st.download_button(
            label="ดาวน์โหลดไฟล์ Excel (Export)",
            data=processed_data,
            file_name=f"Cleaned_{output_name}_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except ValueError as ve:
        st.error(str(ve))
        return
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการประมวลผลโครงสร้างไฟล์: {e}")
        return

def main():
    st.title("DATA CLEANSING SYSTEM")

    st.subheader("1. เลือกธนาคาร")
    selected_bank = st.selectbox("ระบุธนาคารเจ้าของไฟล์:", list(BANK_PASSWORDS.keys()))

    main_acc_num, main_acc_name = "", ""
    if any(bank in selected_bank for bank in ["KTB", "SCB"]):
        st.info("โปรดระบุข้อมูลบัญชีหลักเพื่อใช้เป็นข้อมูลอ้างอิง หรือใช้ประมวลผลทิศทางการโอนเงิน")
        main_acc_num = st.text_input("หมายเลขบัญชีหลัก (10 หลัก):", max_chars=10)
        main_acc_name = st.text_input("ชื่อบัญชีหลัก:")

    st.subheader("2. นำเข้าข้อมูล (Import)")
    uploaded_file = st.file_uploader("ลากไฟล์ Excel หรือ CSV มาวาง หรือคลิกเพื่อเลือกไฟล์", type=['xlsx', 'xls', 'csv'])

    if uploaded_file is not None:
        file_bytes = io.BytesIO(uploaded_file.read())
        filename = uploaded_file.name
        is_encrypted = False
        
        if not filename.lower().endswith('.csv'):
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
                        process_and_allow_download(decrypted_file, selected_bank, filename, main_acc_num, main_acc_name)
                    else:
                        st.error("รหัสผ่านไม่ถูกต้อง กรุณาดำเนินการปลดรหัสด้วยตนเอง")
            else:
                st.error("ไม่ทราบรหัสผ่านสำหรับธนาคารนี้ หรืออาจเป็นไฟล์ที่ไม่มีรหัสมาตรฐาน กรุณาดำเนินการปลดรหัสด้วยตนเอง")
        else:
            st.success("ไฟล์พร้อมดำเนินการ (ไม่มีการเข้ารหัส)")
            file_bytes.seek(0)
            process_and_allow_download(file_bytes, selected_bank, filename, main_acc_num, main_acc_name)

if __name__ == "__main__":
    main()
