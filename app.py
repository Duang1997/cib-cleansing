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
    "ธนาคารทหารไทยธนชาต (TTB)": "Ttb@011"
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
    """ฟังก์ชันเทียบความคล้ายของคำ หากคล้ายเกิน 60% จะเปลี่ยนให้อัตโนมัติ"""
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

    # 1. ตรวจสอบและแก้ไขหัวตาราง TTB อัตโนมัติ (ข้ามชื่อบัญชีไปตรวจแบบยืดหยุ่นภายหลัง)
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

    # 2. ฟังก์ชันค้นหาคอลัมน์ชื่อบัญชีแบบยืดหยุ่น (ตัดช่องว่างและตัวพิมพ์เล็ก-ใหญ่) ครอบคลุม TTB
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
    
    # ใช้งานคอลัมน์ที่ค้นหาด้วยระบบ Flexible Matching
    clean_df['ชื่อบัญชีต้นทาง'] = raw_df[from_name_col].astype(str).replace('nan', '') if from_name_col else ""
    
    clean_df['ชื่อธนาคารปลายทาง'] = raw_df.get('TO BANK CODE', pd.Series(dtype=str)).apply(map_bank)
    clean_df['หมายเลขบัญชีปลายทาง'] = raw_df.get('TO ACCOUNT NO', pd.Series(dtype=str)).astype(str).replace('nan', '')
    
    # ใช้งานคอลัมน์ที่ค้นหาด้วยระบบ Flexible Matching
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
# Main Controller (UI)
# ==========================================
def process_and_allow_download(excel_file, bank_name, ktb_acc_num="", ktb_acc_name=""):
    st.write("---")
    st.subheader("3. การประมวลผล (Processing)")
    
    try:
        warn_msg = ""
        if "KBANK" in bank_name:  
            st.info("กำลังประมวลผลข้อมูลตามโครงสร้างของธนาคารกสิกรไทย (KBANK)...")
            processed_data, df_show, warn_msg = process_kbank(excel_file)
        elif "KTB" in bank_name:
            if not ktb_acc_num or not ktb_acc_name:
                st.warning("ระบบไม่สามารถประมวลผลได้ กรุณากรอก 'หมายเลขบัญชีหลัก' และ 'ชื่อบัญชีหลัก' ด้านบนให้ครบถ้วน")
                return
            st.info("กำลังประมวลผลข้อมูลตามโครงสร้างของธนาคารกรุงไทย (KTB)...")
            processed_data, df_show, warn_msg = process_ktb(excel_file, ktb_acc_num, ktb_acc_name)
        elif "TTB" in bank_name:
            st.info("กำลังประมวลผลข้อมูลตามโครงสร้างของธนาคารทหารไทยธนชาต (TTB)...")
            processed_data, df_show, warn_msg = process_ttb(excel_file)
        else:
            st.error("ไม่พบโครงสร้างการประมวลผลของธนาคารนี้")
            return

        if warn_msg:
            st.warning(warn_msg)

        st.write("ตัวอย่างข้อมูลที่ประมวลผลแล้ว (5 แถวแรก):")
        display_df = df_show.drop(columns=['_source_type']) if '_source_type' in df_show.columns else df_show
        st.dataframe(display_df.head())

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="ดาวน์โหลดไฟล์ Excel (Export)",
            data=processed_data,
            file_name=f"Cleaned_{bank_name.split()[0]}_{timestamp}.xlsx",
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

    ktb_acc_num, ktb_acc_name = "", ""
    if "KTB" in selected_bank:
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
