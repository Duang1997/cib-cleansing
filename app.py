import streamlit as st
import pandas as pd
import numpy as np
import io
import msoffcrypto
import re
from datetime import datetime
import difflib

# 1. การตั้งค่าหน้าเว็บ
st.set_page_config(page_title="ระบบแปลงข้อมูล", page_icon="🏦", layout="centered")

# 2. การตกแต่งด้วย CSS (โทนกรมท่า-ทอง)
custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600&display=swap');
:root {
    --bg: #09101C; --panel: #131E32; --panel-2: #1A2740; --line: #26375A;
    --gold: #D0A83A; --gold-hi: #E6C153; --text: #F8FAFC; --muted: #94A3B8;
}
.stApp { background: radial-gradient(1200px 500px at 50% -10%, #14213A 0%, var(--bg) 60%); font-family: 'Kanit', sans-serif; }
.block-container { padding-top: 2.2rem; max-width: 860px; }
h1, h2, h3 { color: var(--gold) !important; font-family: 'Kanit', sans-serif !important; font-weight: 500; }
h3 { font-size: 1.15rem !important; padding-bottom: .35rem; border-bottom: 1px solid var(--line); margin-top: .6rem !important; }
p, label, li { color: var(--text) !important; font-family: 'Kanit', sans-serif !important; }

/* Hero */
.hero { background: linear-gradient(135deg, var(--panel-2) 0%, var(--panel) 100%); border: 1px solid var(--line);
        border-left: 4px solid var(--gold); border-radius: 12px; padding: 1.1rem 1.4rem; margin-bottom: 1.4rem; }
.hero h1 { margin: 0 !important; padding: 0 !important; font-size: 1.75rem !important; letter-spacing: .5px; }
.hero p { margin: .25rem 0 0 0; color: var(--muted) !important; font-size: .95rem; font-weight: 300; }
.bank-chips { margin-top: .7rem; display: flex; flex-wrap: wrap; gap: .35rem; }
.bank-chips span { font-size: .75rem; color: var(--gold) !important; border: 1px solid #5B4A1C; background: #1F1A0E;
                   border-radius: 999px; padding: .1rem .6rem; }

/* ปุ่ม */
.stButton>button, .stDownloadButton>button { background-color: var(--gold) !important; color: #000 !important; border-radius: 8px;
    border: none; font-weight: 600; width: 100%; padding: .6rem 1rem; transition: background-color .15s ease; }
.stButton>button:hover, .stDownloadButton>button:hover { background-color: var(--gold-hi) !important; }
.stButton>button p, .stDownloadButton>button p { color: #000 !important; }

/* ช่องกรอก / อัปโหลด / เลือก */
[data-testid="stFileUploadDropzone"], [data-testid="stFileUploaderDropzone"] { background-color: var(--panel) !important; border: 2px dashed var(--gold) !important; border-radius: 10px; }
[data-testid="stFileUploadDropzone"] *, [data-testid="stFileUploaderDropzone"] * { color: var(--text) !important; }
.stSelectbox > div > div, .stTextInput input { background-color: var(--panel) !important; border-color: var(--line) !important; color: var(--text) !important; border-radius: 8px; }
.stTextInput input:focus { border-color: var(--gold) !important; }
div[data-baseweb="select"] span, div[data-baseweb="select"] > div > div { color: var(--text) !important; -webkit-text-fill-color: var(--text) !important; }
[data-testid="stFileUploadDropzone"] button, [data-testid="stFileUploaderDropzone"] button { background: var(--gold) !important; border: none !important; }
[data-testid="stFileUploadDropzone"] button *, [data-testid="stFileUploaderDropzone"] button * { color: #000 !important; }
[data-testid="stFileChip"], [data-testid="stFileUploaderFile"] { background: var(--panel-2) !important; border: 1px solid var(--line) !important; }
[data-testid="stFileChip"] *, [data-testid="stFileUploaderFile"] * { color: var(--text) !important; }
[data-testid="stSelectbox"] input, [data-testid="stSelectbox"] svg, [data-testid="stSelectbox"] div[data-baseweb="select"] * { color: var(--text) !important; -webkit-text-fill-color: var(--text) !important; opacity: 1 !important; }
header[data-testid="stHeader"] { background: transparent; }
div[data-baseweb="popover"] ul li, div[data-baseweb="popover"] ul li span { color: #000000 !important; }
div[data-baseweb="popover"] ul li:hover { background-color: var(--gold-hi) !important; color: #000000 !important; }

/* การ์ดสรุป (Metric) */
[data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: .7rem .9rem; }
[data-testid="stMetricLabel"] p { color: var(--muted) !important; font-size: .85rem; }
[data-testid="stMetricValue"] { color: var(--text) !important; font-size: 1.35rem !important; font-weight: 500; }

/* แท็บ + ตาราง */
.stTabs [data-baseweb="tab-list"] { gap: .3rem; }
.stTabs [data-baseweb="tab"] { background: var(--panel); border-radius: 8px 8px 0 0; padding: .35rem .9rem; }
.stTabs [aria-selected="true"] { background: var(--panel-2); border-bottom: 2px solid var(--gold) !important; }
.stTabs [data-baseweb="tab"] p { color: var(--text) !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 8px; }
[data-testid="stCaptionContainer"] p { color: var(--muted) !important; }
hr { border-color: var(--line) !important; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# คอลัมน์มาตรฐานของ Cleaned Data (ใช้ร่วมกันทุกธนาคาร)
NEW_COLUMNS = ['วันที่ทำรายการ', 'เวลาที่ทำรายการ', 'ประเภทรายการ', 'ช่องทาง', 'ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง', 'ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง', 'ยอดเงิน', 'จำนวนครั้ง']

# 3. ฐานข้อมูลรหัสผ่านมาตรฐาน
BANK_PASSWORDS = {
    "ธนาคารกสิกรไทย (KBANK)": "2533*",
    "ธนาคารกรุงไทย (KTB)": "1263",
    "ธนาคารไทยพาณิชย์ (SCB)": "7512",
    "ธนาคารทหารไทยธนชาต (TTB)": "Ttb@011",
    "ธนาคารกรุงเทพ (BBL)": None,
    "ธนาคารออมสิน (GSB)": None,
    "ธนาคารกรุงศรีอยุธยา (BAY)": None,
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
# เครื่องมือตกแต่งชีท Cleaned Data (ใช้ร่วมกันทุกธนาคาร)
# ==========================================
def write_cleaned_header(workbook, worksheet, columns):
    """เขียนหัวตาราง Cleaned Data แบบมีสีพื้นและเส้นขอบ"""
    fmt_header = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter',
                                      'border': 1, 'bg_color': '#1F3864', 'font_color': '#FFFFFF'})
    for c, v in enumerate(columns):
        worksheet.write(0, c, v, fmt_header)

def finalize_cleaned_sheet(worksheet, n_rows, n_cols):
    """ปรับความกว้างคอลัมน์ ตรึงแถวหัวตาราง และเปิดตัวกรอง"""
    worksheet.autofit()
    worksheet.freeze_panes(1, 0)
    if n_rows > 0:
        worksheet.autofilter(0, 0, n_rows, n_cols - 1)

# ==========================================
# ระบบสรุปบัญชีคู่โอน (Pivot ขาเข้า - ขาออก)
# ==========================================
UNKNOWN_ACC = '(ไม่ระบุ)'

def _clean_text(val):
    return '' if pd.isna(val) or str(val).strip().lower() in ['nan', 'none', 'nat', ''] else str(val).strip()

def _account_key(val):
    """แปลงเลขบัญชีให้อยู่ในรูปเทียบกันได้ (ตัดขีด ช่องว่าง .0 และเลข 0 นำหน้า)"""
    s = re.sub(r'\.0$', '', _clean_text(val))
    digits = re.sub(r'[\s-]', '', s)
    return digits.lstrip('0') if digits.isdigit() else s

def _mode_text(series):
    s = series.map(_clean_text)
    s = s[s != '']
    return s.mode().iloc[0] if not s.empty else ''

def _parse_dates(series):
    def to_text(v):
        if isinstance(v, (pd.Timestamp, datetime)) and pd.notna(v):
            return v.strftime('%d/%m/%Y')
        return str(convert_buddhist_year_string(v)).strip()
    return pd.to_datetime(series.apply(to_text), format='%d/%m/%Y', errors='coerce')

def _display_acc(val):
    """เลขบัญชีสำหรับแสดงผล/จัดกลุ่ม: ตัดขีด เว้นวรรค .0 แต่คงเลข 0 นำหน้าไว้"""
    t = re.sub(r'\.0$', '', _clean_text(val))
    compact = re.sub(r'[\s-]', '', t)
    return compact if compact.isdigit() else t

def detect_main_account(df):
    """หาเลขบัญชีหลักจากเลขบัญชีที่ปรากฏบ่อยที่สุดทั้งฝั่งต้นทางและปลายทาง"""
    accs = pd.concat([df['หมายเลขบัญชีต้นทาง'], df['หมายเลขบัญชีปลายทาง']]).map(_clean_text)
    accs = accs[accs.str.replace(r'[\s-]', '', regex=True).str.fullmatch(r'\d{6,}')]
    return accs.mode().iloc[0] if not accs.empty else ''

def build_flow_tables(df, main_account=None, owner_col=None, owner_name_col=None, direction_col=None):
    """
    สร้างตารางสรุปบัญชีคู่โอนจาก Cleaned Data

    โหมดบัญชีหลักเดียว (KBANK, KTB, SCB, TTB, BBL, GSB):
      - โอนเข้า = แถวที่บัญชีปลายทางเป็นบัญชีหลัก → สรุปตามบัญชีต้นทาง
      - โอนออก = แถวที่บัญชีต้นทางเป็นบัญชีหลัก → สรุปตามบัญชีปลายทาง
    โหมดบัญชีเจ้าของรายแถว (PRASAN - ไฟล์เดียวอาจมีหลายบัญชี):
      - ใช้ owner_col เป็นบัญชีเจ้าของของแต่ละแถว และ direction_col (DEPOSIT / WITHDRAWAL) เป็นทิศทาง
      - สรุปแยกตาม (บัญชีเจ้าของ, บัญชีคู่โอน)

    คืนค่า dict: inflow, outflow (DataFrame มีคอลัมน์ 'ทั้งสองทาง'), owners (list), main_account (str)
    """
    work = df.copy()
    work['_amt'] = pd.to_numeric(work['ยอดเงิน'], errors='coerce').fillna(0)
    work['_cnt'] = pd.to_numeric(work['จำนวนครั้ง'], errors='coerce').fillna(1)
    work['_date'] = _parse_dates(work['วันที่ทำรายการ'])
    src_key = work['หมายเลขบัญชีต้นทาง'].map(_account_key)
    dst_key = work['หมายเลขบัญชีปลายทาง'].map(_account_key)

    use_owner = bool(owner_col) and owner_col in work.columns and work[owner_col].map(_clean_text).ne('').any()
    if use_owner:
        work['_owner'] = work[owner_col].map(_display_acc).replace('', UNKNOWN_ACC)
        work['_owner_name'] = work[owner_name_col].map(_clean_text) if owner_name_col in work.columns else ''
        owner_key = work[owner_col].map(_account_key)
        direction = work[direction_col].astype(str).str.upper() if direction_col in work.columns else pd.Series('', index=work.index)
        has_amt = work['_amt'] != 0
        inflow_rows = work[(direction == 'DEPOSIT') & has_amt & (src_key != owner_key)]
        outflow_rows = work[direction.str.startswith('WITHDRAW') & has_amt & (dst_key != owner_key)]
        owners = sorted(work['_owner'].unique())
        main_account = ', '.join(owners)
    else:
        main_account = _clean_text(main_account) or detect_main_account(df)
        main_key = _account_key(main_account)
        if main_key:
            inflow_rows = work[(dst_key == main_key) & (src_key != main_key)]
            outflow_rows = work[(src_key == main_key) & (dst_key != main_key)]
        else:
            inflow_rows = outflow_rows = work.iloc[0:0]
        owners = [main_account] if main_account else []

    multi_owner = use_owner and len(owners) > 1
    group_keys = (['_owner'] if multi_owner else []) + ['_acc']
    base_cols = ['เลขบัญชี', 'ธนาคาร', 'ชื่อบัญชี', 'ยอดเงิน', 'จำนวนครั้ง', 'วันแรก', 'วันสุดท้าย']
    out_cols = (['บัญชีหลัก', 'ชื่อบัญชีหลัก'] if multi_owner else []) + base_cols

    def summarize(part, bank_col, acc_col, name_col):
        if part.empty:
            return pd.DataFrame(columns=out_cols)
        part = part.copy()
        part['_acc'] = part[acc_col].map(_display_acc).replace('', UNKNOWN_ACC)
        # ใช้ dict เพราะชื่อคอลัมน์ภาษาไทยบางคำ (เช่น "จำนวนครั้ง") ถูก Python แปลงรูปเมื่อเขียนเป็น keyword ตรง ๆ
        spec = {
            'ธนาคาร': (bank_col, _mode_text),
            'ชื่อบัญชี': (name_col, _mode_text),
            'ยอดเงิน': ('_amt', 'sum'),
            'จำนวนครั้ง': ('_cnt', 'sum'),
            'วันแรก': ('_date', 'min'),
            'วันสุดท้าย': ('_date', 'max'),
        }
        if multi_owner:
            spec['ชื่อบัญชีหลัก'] = ('_owner_name', _mode_text)
        table = part.groupby(group_keys, sort=False).agg(**spec).reset_index()
        table = table.rename(columns={'_acc': 'เลขบัญชี', '_owner': 'บัญชีหลัก'})
        sort_by = (['บัญชีหลัก'] if multi_owner else []) + ['ยอดเงิน', 'จำนวนครั้ง']
        ascending = ([True] if multi_owner else []) + [False, False]
        return table.sort_values(sort_by, ascending=ascending).reset_index(drop=True)[out_cols]

    inflow = summarize(inflow_rows, 'ชื่อธนาคารต้นทาง', 'หมายเลขบัญชีต้นทาง', 'ชื่อบัญชีต้นทาง')
    outflow = summarize(outflow_rows, 'ชื่อธนาคารปลายทาง', 'หมายเลขบัญชีปลายทาง', 'ชื่อบัญชีปลายทาง')

    # บัญชีที่มีทั้งโอนเข้าและรับโอนออก (กรณีหลายบัญชีหลัก เทียบภายในบัญชีหลักเดียวกัน)
    key_cols = (['บัญชีหลัก'] if multi_owner else []) + ['เลขบัญชี']
    keys = lambda t: set(map(tuple, t[key_cols].values.tolist()))
    both = (keys(inflow) & keys(outflow)) - {k for k in keys(inflow) if k[-1] == UNKNOWN_ACC}
    for t in (inflow, outflow):
        t['ทั้งสองทาง'] = [tuple(k) in both for k in t[key_cols].values.tolist()]
    return {'inflow': inflow, 'outflow': outflow, 'both_count': len(both),
            'owners': owners, 'multi_owner': multi_owner, 'main_account': main_account}

def write_pivot_sheet(writer, df, main_account=None, main_account_name='', sheet_name='Pivot', **flow_kwargs):
    """เขียนชีท Pivot: ตารางโอนเข้า (ซ้าย) และโอนออก (ขวา) เรียงตามยอดเงินมากไปน้อย"""
    flows = build_flow_tables(df, main_account, **flow_kwargs)
    wb = writer.book
    ws = wb.add_worksheet(sheet_name)

    base = {'font_name': 'Tahoma', 'font_size': 10, 'valign': 'vcenter'}
    F = lambda **kw: wb.add_format({**base, **kw})
    f_title = F(bold=True, font_size=14, font_color='#1F3864')
    f_sub   = F(italic=True, font_color='#595959')
    f_head  = F(bold=True, align='center', border=1, bg_color='#D9E1F2', text_wrap=True)
    f_total_lbl = F(bold=True, border=1, bg_color='#FFF2CC')
    f_total_num = F(bold=True, border=1, bg_color='#FFF2CC', num_format='#,##0.00')
    f_total_int = F(bold=True, border=1, bg_color='#FFF2CC', num_format='#,##0', align='center')
    styles = {}
    for key, bg in (('row', None), ('both', '#FCE4D6')):
        extra = {'bg_color': bg} if bg else {}
        styles[key] = {
            'int':  F(border=1, align='center', num_format='0', **extra),
            'txt':  F(border=1, num_format='@', **extra),
            'num':  F(border=1, num_format='#,##0.00', **extra),
            'cnt':  F(border=1, num_format='#,##0', align='center', **extra),
            'date': F(border=1, num_format='dd/mm/yyyy', align='center', **extra),
            'mark': F(border=1, align='center', bold=True, font_color='#C55A11', **extra),
        }

    if flows['multi_owner']:
        acc_label = f"{len(flows['owners'])} บัญชี ({flows['main_account']})"
    else:
        acc_label = flows['main_account'] + (f' {main_account_name}' if main_account_name else '')
    ws.write(0, 0, f'สรุปบัญชีคู่โอน (Pivot ขาเข้า - ขาออก) บัญชีหลัก: {acc_label}', f_title)
    ws.write(1, 0, 'ที่มา: ชีท Cleaned Data · เรียงตามยอดเงินจากมากไปน้อย · ✓ แถวสีส้ม = บัญชีที่มีทั้งโอนเข้าและรับโอนออก · ชื่อบัญชีใช้ชื่อที่พบบ่อยที่สุดของเลขบัญชีนั้น', f_sub)

    # (หัวคอลัมน์, ความกว้าง, ชนิด, คอลัมน์ข้อมูล)
    spec = [('ลำดับ', 7, 'int', None)]
    if flows['multi_owner']:
        spec += [('บัญชีหลัก', 16, 'txt', 'บัญชีหลัก'), ('ชื่อบัญชีหลัก', 28, 'txt', 'ชื่อบัญชีหลัก')]
    spec += [('เลขบัญชี', 16, 'txt', 'เลขบัญชี'), ('ธนาคาร', 10, 'txt', 'ธนาคาร'), ('ชื่อบัญชี', 40, 'txt', 'ชื่อบัญชี'),
             ('ยอดเงิน (บาท)', 16, 'num', 'ยอดเงิน'), ('จำนวนครั้ง', 10, 'cnt', 'จำนวนครั้ง'),
             ('วันแรก', 12, 'date', 'วันแรก'), ('วันสุดท้าย', 12, 'date', 'วันสุดท้าย'),
             ('เข้า-ออก\nทั้งสองทาง', 11, 'mark', 'ทั้งสองทาง')]
    width = len(spec)
    pos = {s[3]: i for i, s in enumerate(spec)}
    blocks = [(flows['inflow'], 0, 'โอนเข้า (บัญชีต้นทางที่โอนเข้าบัญชีหลัก)', '#2F5597'),
              (flows['outflow'], width + 1, 'โอนออก (บัญชีปลายทางที่บัญชีหลักโอนออกไป)', '#C55A11')]

    for table, c0, title, color in blocks:
        ws.merge_range(3, c0, 3, c0 + width - 1, title, F(bold=True, font_size=12, font_color='#FFFFFF', bg_color=color, align='center'))
        for i, (h, w, _, _) in enumerate(spec):
            ws.write(4, c0 + i, h, f_head)
            ws.set_column(c0 + i, c0 + i, w)

        n = len(table)
        first, last = 6, 6 + max(n, 1) - 1
        rng = lambda key: f'{xl_col(c0 + pos[key])}{first + 1}:{xl_col(c0 + pos[key])}{last + 1}'
        for i in range(width):
            ws.write(5, c0 + i, '', f_total_lbl)
        ws.write(5, c0, 'รวมทั้งหมด', f_total_lbl)
        ws.write(5, c0 + pos['ชื่อบัญชี'], f'{n:,} บัญชี', f_total_lbl)
        ws.write_formula(5, c0 + pos['ยอดเงิน'], f'=SUM({rng("ยอดเงิน")})', f_total_num, float(table['ยอดเงิน'].sum()) if n else 0)
        ws.write_formula(5, c0 + pos['จำนวนครั้ง'], f'=SUM({rng("จำนวนครั้ง")})', f_total_int, float(table['จำนวนครั้ง'].sum()) if n else 0)
        ws.write_formula(5, c0 + pos['ทั้งสองทาง'], f'=COUNTIF({rng("ทั้งสองทาง")},"✓")', f_total_int, int(table['ทั้งสองทาง'].sum()) if n else 0)

        if n == 0:
            ws.write(first, c0, 'ไม่พบรายการ', styles['row']['txt'])
            continue

        for k, rec in enumerate(table.to_dict('records')):
            r = first + k
            st_ = styles['both'] if rec['ทั้งสองทาง'] else styles['row']
            for i, (_, _, kind, col) in enumerate(spec):
                c = c0 + i
                if col is None:
                    ws.write_number(r, c, k + 1, st_[kind])
                elif kind == 'mark':
                    ws.write_string(r, c, '✓' if rec[col] else '', st_[kind])
                elif kind == 'date':
                    d = rec[col]
                    if pd.notna(d): ws.write_datetime(r, c, d.to_pydatetime(), st_[kind])
                    else: ws.write_blank(r, c, None, st_[kind])
                elif kind in ('num', 'cnt'):
                    ws.write_number(r, c, float(rec[col]), st_[kind])
                else:
                    ws.write_string(r, c, str(rec[col]), st_[kind])

    ws.set_column(width, width, 3)   # ช่องว่างคั่นระหว่างสองตาราง
    ws.set_row(4, 30)
    ws.freeze_panes(6, 0)
    return flows

def xl_col(idx):
    """แปลงเลขคอลัมน์ (เริ่ม 0) เป็นตัวอักษร Excel เช่น 0 → A"""
    name = ''
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        name = chr(65 + rem) + name
    return name

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

    new_columns = NEW_COLUMNS.copy()
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

        write_cleaned_header(writer.book, ws_cleaned, new_columns)

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
        finalize_cleaned_sheet(ws_cleaned, len(df_cleaned_ready), len(new_columns))
        write_pivot_sheet(writer, df_cleaned_ready, kbank_acc_num, kbank_acc_name)
        
    df_cleaned_ready.attrs['main_account'] = kbank_acc_num
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

    new_columns = NEW_COLUMNS.copy()
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
        
        fmt_txt  = writer.book.add_format({'num_format': '@'}) 
        fmt_green = writer.book.add_format({'num_format': '#,##0.00', 'font_color': '#006400', 'bold': True})
        fmt_red   = writer.book.add_format({'num_format': '#,##0.00', 'font_color': '#FF0000', 'bold': True})
        fmt_normal = writer.book.add_format({'num_format': '#,##0.00'})
        fmt_date = writer.book.add_format({'num_format': '@', 'align': 'center'})

        write_cleaned_header(writer.book, ws, df_cleaned.columns)

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
        finalize_cleaned_sheet(ws, len(df_cleaned), len(df_cleaned.columns))
        write_pivot_sheet(writer, df_cleaned, account_number, account_name)

    df_cleaned.attrs['main_account'] = account_number
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

    new_columns = NEW_COLUMNS.copy()
    clean_df = clean_df.reindex(columns=new_columns + ['_source_type'])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        raw_df_original.to_excel(writer, sheet_name='Sheet1_RawData', index=False)
        ws_cleaned = writer.book.add_worksheet('Sheet2_Cleaned Data')
        
        g_fmt = writer.book.add_format({'font_color': 'green', 'num_format': '#,##0.00'})
        r_fmt = writer.book.add_format({'font_color': 'red', 'num_format': '#,##0.00'})
        d_fmt = writer.book.add_format({'num_format': 'General'})
        t_fmt = writer.book.add_format({'num_format': '@'})

        write_cleaned_header(writer.book, ws_cleaned, new_columns)

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
        finalize_cleaned_sheet(ws_cleaned, len(clean_df), len(new_columns))
        flows = write_pivot_sheet(writer, clean_df, sheet_name='Sheet3_Pivot')
        
    clean_df.attrs['main_account'] = flows['main_account']
    return output.getvalue(), clean_df, warn_msg

# ==========================================
# ส่วนประมวลผล BBL (ปรับปรุงการดึง Header)
# ==========================================
def process_bbl(excel_file):
    df_temp = pd.read_excel(excel_file, header=None, nrows=10)
    header_row_idx = 0
    for i, row in df_temp.iterrows():
        if row.astype(str).str.contains('Txdate|Tx Date', case=False, na=False).any():
            header_row_idx = i
            break

    excel_file.seek(0)
    df_orig = pd.read_excel(excel_file, header=header_row_idx, dtype=str)
    
    excel_file.seek(0)
    df_orig_copy = pd.read_excel(excel_file, sheet_name=0, header=None)

    df_orig.columns = [str(c).replace('\n', ' ').strip() for c in df_orig.columns]

    # การใช้ Substring Matching ตามโครงสร้างเดิมเพื่อหลีกเลี่ยง Error หากคอลัมน์หายไป
    cols_needed = ['Txdate', 'Txtime', 'Txtype', 'Tx channel', 'From bankcode', 
                   'From account-no', 'From account-name', 'To bankcode', 
                   'To account-no', 'To account-name', 'Deposit', 'Withdrawal']
    
    renamed_info = []
    for col in cols_needed:
        if col not in df_orig.columns:
            found = False
            for c in df_orig.columns:
                if col.replace(' ', '').lower() in str(c).replace(' ', '').lower():
                    df_orig.rename(columns={c: col}, inplace=True)
                    renamed_info.append(f"[{c}] ➔ [{col}]")
                    found = True
                    break
            if not found:
                # สร้างคอลัมน์เปล่าเพื่อไม่ให้เกิด Error หากธนาคารซ่อนคอลัมน์นั้นไป
                df_orig[col] = np.nan 

    warn_msg = "ระบบได้ทำการปรับแก้หัวตารางอัตโนมัติ:\n" + " | ".join(renamed_info) if renamed_info else ""

    def map_bbl_bank(bank_name):
        if pd.isna(bank_name) or str(bank_name).strip().lower() == "nan": return ""
        b = str(bank_name).strip().upper()
        if 'KBNK' in b or 'KASIKORN' in b: return 'KBANK'
        if 'SCB' in b or 'SIAM COM' in b: return 'SCB'
        if 'BBL' in b or 'BANGKOK' in b: return 'BBL'
        if 'KTB' in b or 'KRUNG THAI' in b: return 'KTB'
        if 'BAY' in b or 'KRUNGSRI' in b: return 'BAY'
        if 'TTB' in b or 'TMB' in b or 'THANACHART' in b: return 'TTB'
        if 'GSB' in b or 'GOVERNMENT SAVING' in b: return 'GSB'
        return b

    df_new = pd.DataFrame()
    df_new['วันที่ทำรายการ'] = df_orig['Txdate'].apply(convert_buddhist_year_string)
    df_new['วันที่ทำรายการ'] = pd.to_datetime(df_new['วันที่ทำรายการ'], format='%d/%m/%Y', errors='coerce')
    
    df_new['เวลาที่ทำรายการ'] = df_orig['Txtime'].fillna('').astype(str).replace('nan', '')
    df_new['ประเภทรายการ'] = df_orig['Txtype'].fillna('').astype(str).replace('nan', '')
    df_new['ช่องทาง'] = df_orig['Tx channel'].fillna('').astype(str).replace('nan', '')

    df_new['ชื่อธนาคารต้นทาง'] = df_orig['From bankcode'].apply(map_bbl_bank)
    df_new['หมายเลขบัญชีต้นทาง'] = df_orig['From account-no'].apply(lambda x: str(x).strip().replace('.0','') if pd.notna(x) and str(x).lower() != 'nan' else '')
    df_new['ชื่อบัญชีต้นทาง'] = df_orig['From account-name'].apply(lambda x: str(x).strip() if pd.notna(x) and str(x).lower() != 'nan' else '')
    
    df_new['ชื่อธนาคารปลายทาง'] = df_orig['To bankcode'].apply(map_bbl_bank)
    df_new['หมายเลขบัญชีปลายทาง'] = df_orig['To account-no'].apply(lambda x: str(x).strip().replace('.0','') if pd.notna(x) and str(x).lower() != 'nan' else '')
    df_new['ชื่อบัญชีปลายทาง'] = df_orig['To account-name'].apply(lambda x: str(x).strip() if pd.notna(x) and str(x).lower() != 'nan' else '')

    df_orig['Deposit_num'] = pd.to_numeric(df_orig['Deposit'].astype(str).replace({',': ''}, regex=True), errors='coerce').fillna(0)
    df_orig['Withdrawal_num'] = pd.to_numeric(df_orig['Withdrawal'].astype(str).replace({',': ''}, regex=True), errors='coerce').fillna(0)
    
    df_new['ยอดเงิน'] = df_orig['Deposit_num'] + df_orig['Withdrawal_num']
    df_new['จำนวนครั้ง'] = 1

    all_acc_no = pd.concat([df_new[df_new['หมายเลขบัญชีต้นทาง'] != '']['หมายเลขบัญชีต้นทาง'], df_new[df_new['หมายเลขบัญชีปลายทาง'] != '']['หมายเลขบัญชีปลายทาง']])
    top_acc_no = all_acc_no.mode()[0] if not all_acc_no.empty else ""

    all_acc_name = pd.concat([df_new[df_new['ชื่อบัญชีต้นทาง'] != '']['ชื่อบัญชีต้นทาง'], df_new[df_new['ชื่อบัญชีปลายทาง'] != '']['ชื่อบัญชีปลายทาง']])
    top_acc_name = all_acc_name.mode()[0] if not all_acc_name.empty else ""

    df_new['_source_type'] = 'UNKNOWN'

    for idx in df_new.index:
        dep = df_orig.at[idx, 'Deposit_num']
        wtd = df_orig.at[idx, 'Withdrawal_num']
        
        acc_from = df_new.at[idx, 'หมายเลขบัญชีต้นทาง']
        acc_to = df_new.at[idx, 'หมายเลขบัญชีปลายทาง']
        
        acc_from_empty = (acc_from == '')
        acc_to_empty = (acc_to == '')
        
        if dep > 0:
            df_new.at[idx, '_source_type'] = 'DEPOSIT'
            if acc_from_empty or acc_to_empty:
                df_new.at[idx, 'หมายเลขบัญชีต้นทาง'] = df_new.at[idx, 'ประเภทรายการ']
                df_new.at[idx, 'ชื่อธนาคารปลายทาง'] = 'BBL'
                df_new.at[idx, 'หมายเลขบัญชีปลายทาง'] = top_acc_no
                df_new.at[idx, 'ชื่อบัญชีปลายทาง'] = top_acc_name
                
        elif wtd > 0:
            df_new.at[idx, '_source_type'] = 'WITHDRAWAL'
            if acc_from_empty or acc_to_empty:
                df_new.at[idx, 'หมายเลขบัญชีปลายทาง'] = df_new.at[idx, 'ประเภทรายการ']
                df_new.at[idx, 'ชื่อธนาคารต้นทาง'] = 'BBL'
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

        new_cols = NEW_COLUMNS.copy()
        
        write_cleaned_header(writer.book, ws_cleaned, new_cols)

        for r_num, r_data in df_new.iterrows():
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
        finalize_cleaned_sheet(ws_cleaned, len(df_new), len(new_cols))
        write_pivot_sheet(writer, df_new, top_acc_no, top_acc_name, sheet_name='Sheet3 (Pivot)')
        
    df_new.attrs['main_account'] = top_acc_no
    return output.getvalue(), df_new, warn_msg

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

        new_cols = NEW_COLUMNS.copy()
        
        write_cleaned_header(writer.book, ws_cleaned, new_cols)

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
        finalize_cleaned_sheet(ws_cleaned, len(df_new), len(new_cols))
        write_pivot_sheet(writer, df_new, top_acc_no, top_acc_name, sheet_name='Sheet3 (Pivot)')
        
    df_new.attrs['main_account'] = top_acc_no
    return output.getvalue(), df_new, warn_msg

# ==========================================
# ส่วนประมวลผล PRASAN (ระบบประสาน)
# ==========================================
def process_prasan(excel_file):
    # อ่านคอลัมน์เลขบัญชีเป็นข้อความ เพื่อไม่ให้เลข 0 นำหน้าหาย (เช่น 0222222222 → 222222222)
    header_cols = pd.read_excel(excel_file, sheet_name=0, nrows=0).columns
    acc_dtypes = {c: str for c in header_cols if str(c).lower().strip() in ('fromaccountno', 'toaccountno', 'accountno')}
    excel_file.seek(0)
    df_for_clean = pd.read_excel(excel_file, sheet_name=0, header=0, dtype=acc_dtypes)
    excel_file.seek(0)
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

    new_columns = NEW_COLUMNS.copy()
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
    
    # บัญชีเจ้าของรายแถว (ไฟล์ประสานอาจรวมหลายบัญชีไว้ในไฟล์เดียว) ใช้สำหรับชีท Pivot เท่านั้น ไม่เขียนลง Cleaned Data
    if 'accountno' in df_for_clean.columns:
        df_cleaned['_owner_acc'] = clean_string_or_nan(df_for_clean['accountno'], is_account_no=True)
        df_cleaned['_owner_name'] = clean_string_or_nan(df_for_clean['accountname']) if 'accountname' in df_for_clean.columns else ''
    owner_kwargs = {'owner_col': '_owner_acc', 'owner_name_col': '_owner_name', 'direction_col': source_column}

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

        write_cleaned_header(writer.book, ws_cleaned, new_columns)

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
        finalize_cleaned_sheet(ws_cleaned, len(df_cleaned_ready), len(new_columns))
        flows = write_pivot_sheet(writer, df_cleaned_ready, sheet_name='Sheet3 (Pivot)', **owner_kwargs)
        
    df_cleaned_ready.attrs['main_account'] = flows['main_account']
    df_cleaned_ready.attrs['flow_kwargs'] = owner_kwargs
    return output.getvalue(), df_cleaned_ready, warn_msg

# ==========================================
# ส่วนประมวลผล BAY (ธนาคารกรุงศรีอยุธยา - รายการจากระบบ Switch / TLF)
# ==========================================
BAY_BANK_CODES = {'002': 'BBL', '004': 'KBANK', '006': 'KTB', '011': 'TTB', '014': 'SCB', '017': 'CITI', '022': 'CIMBT',
                  '024': 'UOB', '025': 'BAY', '030': 'GSB', '033': 'GHB', '034': 'BAAC', '065': 'TBANK', '066': 'IBANK',
                  '067': 'TISCO', '069': 'KKP', '070': 'ICBCT', '071': 'TCRB', '073': 'LHBA'}

# รหัส TRANS_TYPE ที่พบในไฟล์ (ตีความจากรูปแบบข้อมูล หากพบรหัสใหม่ระบบจะแสดงเป็น "รหัส xx")
BAY_TRANS_TYPES = {'10': 'ถอนเงินสด ATM', '41': 'โอนเงินภายในธนาคาร', '47': 'ฝากเงินสด',
                   '48': 'โอนเงินต่างธนาคาร/พร้อมเพย์', '49': 'โอนเงินต่างธนาคาร',
                   '50': 'ชำระเงิน/บิล', '55': 'ชำระเงิน/บิล ต่างธนาคาร'}

BAY_CHANNELS = {'MSIM': 'Mobile Banking', 'ENET': 'Internet Banking', 'EATM': 'ATM', 'EKCS': 'ตู้ฝากเงิน (Kiosk)', 'ELTS': 'ตู้ฝากเงิน'}

def process_bay(excel_file, main_acc_num="", main_acc_name=""):
    df_raw = pd.read_excel(excel_file, sheet_name=0, header=None, dtype=str)

    # หาแถวหัวตาราง (แถวที่มีคำว่า PROCESS_DATE)
    header_idx = next((i for i, row in df_raw.iterrows()
                       if row.astype(str).str.upper().str.contains('PROCESS_DATE', na=False).any()), None)
    if header_idx is None:
        raise ValueError("⚠️ ไม่พบหัวตาราง PROCESS_DATE กรุณาตรวจสอบว่าเป็นไฟล์รายการธุรกรรมของธนาคารกรุงศรี (BAY)")

    df = df_raw.iloc[header_idx + 1:].copy()
    df.columns = [str(c).strip().upper() for c in df_raw.iloc[header_idx].values]
    df = df.loc[:, [c for c in df.columns if c not in ('', 'NAN')]].reset_index(drop=True)

    expected_headers = ['PROCESS_DATE', 'PROCESS_TIME', 'TRANS_TYPE', 'FROM_CHANNEL', 'RESPONSE_CODE', 'REQUEST_AMT',
                        'CARD_BANK', 'FR_AC_NUMBER', 'FR_AC_NAME', 'TO_BANK', 'TO_AC_NUMBER', 'TO_AC_NAME']
    missing, renamed = fix_and_validate_headers(df, expected_headers)
    if missing:
        raise ValueError(f"⚠️ รูปแบบหัวตารางไม่ถูกต้อง! \nระบบต้องการคอลัมน์: {', '.join(missing)} \nกรุณาแก้ไขชื่อหัวตารางในไฟล์ Excel ให้ตรงตามรูปแบบก่อนทำรายการ")
    warn_parts = ["ระบบได้ทำการปรับแก้หัวตารางอัตโนมัติ:\n" + " | ".join(renamed)] if renamed else []

    def txt(col):
        return df[col].map(_clean_text) if col in df.columns else pd.Series([''] * len(df))

    def clean_acc(val):
        s = re.sub(r'\.0$', '', _clean_text(val))
        return '' if (s == '' or set(s) == {'0'}) else s     # 0000000000 = ไม่มีบัญชี (เช่น ฝากเงินสด)

    def map_bank(code):
        c = _clean_text(code)
        if not c: return ''
        c = c.zfill(3)[-3:]
        return 'BAY' if c == '000' else BAY_BANK_CODES.get(c, c)   # TO_BANK 0000 = ภายในกรุงศรี

    def parse_date(val):
        # รองรับทั้ง 2025-01-31 (ค.ศ./พ.ศ.) และ 31/01/2568
        v = _clean_text(val)
        m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})', v)
        if m:
            y = int(m.group(1)); y = y - 543 if y > 2400 else y
            return pd.Timestamp(year=y, month=int(m.group(2)), day=int(m.group(3)))
        return pd.to_datetime(convert_buddhist_year_string(v), format='%d/%m/%Y', errors='coerce')

    def fmt_time(t):
        t = _clean_text(t).split('.')[0]
        return f"{t.zfill(6)[:2]}:{t.zfill(6)[2:4]}:{t.zfill(6)[4:6]}" if t.isdigit() else t

    # --- แยกรายการที่ไม่สำเร็จ (RESPONSE_CODE ไม่ใช่ 00) ออกเป็นชีทต่างหาก ---
    resp = txt('RESPONSE_CODE')
    ok_mask = resp.isin(['00', '0', '000', ''])
    df_failed = df[~ok_mask].copy()
    df = df[ok_mask].reset_index(drop=True)
    if len(df_failed):
        warn_parts.append(f"พบรายการที่ไม่สำเร็จ (RESPONSE_CODE ≠ 00) จำนวน {len(df_failed):,} รายการ ไม่นำมาคำนวณ แยกไว้ในชีท 'รายการไม่สำเร็จ'")

    fr_acc = df['FR_AC_NUMBER'].map(clean_acc)
    to_acc = df['TO_AC_NUMBER'].map(clean_acc)

    # --- บัญชีหลัก: ใช้ที่ผู้ใช้กรอก ถ้าไม่กรอกใช้เลขบัญชีที่พบบ่อยที่สุด ---
    if main_acc_num:
        f_acc = str(main_acc_num).strip()
    else:
        all_acc = pd.concat([fr_acc, to_acc]); all_acc = all_acc[all_acc != '']
        f_acc = all_acc.mode().iloc[0] if not all_acc.empty else ''
    main_key = _account_key(f_acc)
    is_out = fr_acc.map(_account_key) == main_key
    is_in = (to_acc.map(_account_key) == main_key) & ~is_out
    if main_acc_name:
        f_name = str(main_acc_name).strip()
    else:
        f_name = _mode_text(pd.concat([txt('FR_AC_NAME')[is_out], txt('TO_AC_NAME')[is_in]]))

    type_code = txt('TRANS_TYPE')
    type_label = type_code.map(lambda c: BAY_TRANS_TYPES.get(c, f'รหัส {c}' if c else ''))
    channel = txt('FROM_CHANNEL').map(lambda c: BAY_CHANNELS.get(c, c))
    location = txt('TERM_LOCATION')
    channel = np.where((txt('FROM_CHANNEL') == 'EATM') & (location != ''), channel + ' · ' + location, channel)

    df_cleaned = pd.DataFrame({
        'วันที่ทำรายการ': df['PROCESS_DATE'].map(parse_date),
        'เวลาที่ทำรายการ': df['PROCESS_TIME'].map(fmt_time),
        'ประเภทรายการ': type_label,
        'ช่องทาง': channel,
        'ชื่อธนาคารต้นทาง': df['CARD_BANK'].map(map_bank),
        'หมายเลขบัญชีต้นทาง': fr_acc,
        'ชื่อบัญชีต้นทาง': txt('FR_AC_NAME'),
        'ชื่อธนาคารปลายทาง': df['TO_BANK'].map(map_bank),
        'หมายเลขบัญชีปลายทาง': to_acc,
        'ชื่อบัญชีปลายทาง': txt('TO_AC_NAME'),
        'ยอดเงิน': pd.to_numeric(df['REQUEST_AMT'].astype(str).str.replace(',', ''), errors='coerce').fillna(0),
        'จำนวนครั้ง': 1,
    })

    # เติมช่องว่างแบบเดียวกับธนาคารอื่น: ฝั่งที่ไม่มีบัญชี ใส่ประเภทรายการแทน (เช่น ถอนเงินสด ATM / ฝากเงินสด)
    no_src = df_cleaned['หมายเลขบัญชีต้นทาง'] == ''
    no_dst = df_cleaned['หมายเลขบัญชีปลายทาง'] == ''
    df_cleaned.loc[no_src & is_in, 'หมายเลขบัญชีต้นทาง'] = df_cleaned['ประเภทรายการ']
    df_cleaned.loc[no_src & is_in, 'ชื่อธนาคารต้นทาง'] = ''
    df_cleaned.loc[no_dst & is_out, 'หมายเลขบัญชีปลายทาง'] = df_cleaned['ประเภทรายการ']
    df_cleaned.loc[no_dst & is_out, 'ชื่อธนาคารปลายทาง'] = ''
    # ชื่อบัญชีหลักที่ว่าง เติมให้ครบ
    df_cleaned.loc[is_out & (df_cleaned['ชื่อบัญชีต้นทาง'] == ''), 'ชื่อบัญชีต้นทาง'] = f_name
    df_cleaned.loc[is_in & (df_cleaned['ชื่อบัญชีปลายทาง'] == ''), 'ชื่อบัญชีปลายทาง'] = f_name

    df_cleaned['_source_type'] = np.where(is_in, 'DEPOSIT', 'WITHDRAWAL')
    df_cleaned['_sort_time'] = df_cleaned['เวลาที่ทำรายการ']
    df_cleaned = df_cleaned.sort_values(['วันที่ทำรายการ', '_sort_time'], na_position='first', kind='stable').drop(columns='_sort_time').reset_index(drop=True)
    df_cleaned['วันที่ทำรายการ'] = df_cleaned['วันที่ทำรายการ'].astype(object).where(pd.notna(df_cleaned['วันที่ทำรายการ']), '')

    new_columns = NEW_COLUMNS.copy()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_raw.to_excel(writer, sheet_name='Original', index=False, header=False)
        ws_cleaned = writer.book.add_worksheet('Cleaned Data')

        g_fmt = writer.book.add_format({'font_color': 'green', 'num_format': '#,##0.00'})
        r_fmt = writer.book.add_format({'font_color': 'red', 'num_format': '#,##0.00'})
        d_fmt = writer.book.add_format({'num_format': 'General'})
        dt_fmt = writer.book.add_format({'num_format': 'dd/mm/yyyy'})
        t_fmt = writer.book.add_format({'num_format': '@'})

        write_cleaned_header(writer.book, ws_cleaned, new_columns)

        for r_num, r_data in df_cleaned.iterrows():
            src = r_data['_source_type']
            for c_num, c_name in enumerate(new_columns):
                c_val = r_data[c_name]
                if c_name == 'ยอดเงิน':
                    ws_cleaned.write_number(r_num + 1, c_num, float(c_val), g_fmt if src == 'DEPOSIT' else r_fmt)
                elif c_name == 'จำนวนครั้ง':
                    ws_cleaned.write_number(r_num + 1, c_num, int(c_val), d_fmt)
                elif c_name == 'วันที่ทำรายการ' and isinstance(c_val, (pd.Timestamp, datetime)):
                    ws_cleaned.write_datetime(r_num + 1, c_num, c_val, dt_fmt)
                elif c_name in ['หมายเลขบัญชีต้นทาง', 'หมายเลขบัญชีปลายทาง']:
                    ws_cleaned.write_string(r_num + 1, c_num, str(c_val), t_fmt)
                else:
                    ws_cleaned.write_string(r_num + 1, c_num, str(c_val), d_fmt)
        finalize_cleaned_sheet(ws_cleaned, len(df_cleaned), len(new_columns))
        write_pivot_sheet(writer, df_cleaned, f_acc, f_name)

        if len(df_failed):
            ws_failed = writer.book.add_worksheet('รายการไม่สำเร็จ')
            write_cleaned_header(writer.book, ws_failed, list(df_failed.columns))
            for r_num, row in enumerate(df_failed.itertuples(index=False), start=1):
                for c_num, val in enumerate(row):
                    ws_failed.write_string(r_num, c_num, _clean_text(val), t_fmt)
            finalize_cleaned_sheet(ws_failed, len(df_failed), len(df_failed.columns))

    df_cleaned.attrs['main_account'] = f_acc
    return output.getvalue(), df_cleaned, "\n".join(warn_parts)

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
        xls = pd.ExcelFile(excel_file)
        valid_df = None
        for sheet in xls.sheet_names:
            temp_df = pd.read_excel(xls, sheet_name=sheet, header=None, dtype=str)
            for i, row in temp_df.iterrows():
                row_str = " ".join([str(val).strip().lower() for val in row.values])
                if ('tran_date' in row_str and 'dr_cr_ind' in row_str) or ('date' in row_str and 'debit' in row_str and 'credit' in row_str):
                    valid_df = temp_df
                    break
            if valid_df is not None:
                break
        
        if valid_df is not None:
            raw_df = valid_df
        else:
            excel_file.seek(0)
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

    new_cols = NEW_COLUMNS.copy()
    
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

        write_cleaned_header(writer.book, ws_cleaned, new_cols)

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
        finalize_cleaned_sheet(ws_cleaned, len(res_all), len(new_cols))
        write_pivot_sheet(writer, res_all, f_acc, f_name, sheet_name='Sheet3 (Pivot)')
        
    res_all.attrs['main_account'] = f_acc
    return output.getvalue(), res_all, ""

# ==========================================
# Main Controller (UI)
# ==========================================
def show_flow_summary(df, main_account=None, top_n=10, **flow_kwargs):
    """แสดงสรุป Pivot ขาเข้า-ขาออกบนหน้าเว็บ (ข้อมูลชุดเดียวกับชีท Pivot ในไฟล์ Excel)"""
    flows = build_flow_tables(df, main_account, **flow_kwargs)
    inflow, outflow = flows['inflow'], flows['outflow']

    st.subheader("สรุปบัญชีคู่โอน (Pivot ขาเข้า - ขาออก)")
    if not flows['main_account']:
        st.warning("ไม่พบเลขบัญชีหลัก จึงสรุปทิศทางการโอนไม่ได้")
        return
    if flows['multi_owner']:
        st.caption(f"ไฟล์นี้มีบัญชีหลัก {len(flows['owners'])} บัญชี: {flows['main_account']} · ตารางเต็มแยกตามบัญชีหลักอยู่ในชีท Pivot ของไฟล์ที่ดาวน์โหลด")
    else:
        st.caption(f"บัญชีหลัก: {flows['main_account']} · ตารางเต็มอยู่ในชีท Pivot ของไฟล์ที่ดาวน์โหลด")

    c1, c2, c3 = st.columns(3)
    c1.metric(f"🟢 โอนเข้า · {len(inflow):,} บัญชี / {int(inflow['จำนวนครั้ง'].sum()):,} ครั้ง", f"{inflow['ยอดเงิน'].sum():,.2f} ฿")
    c2.metric(f"🔴 โอนออก · {len(outflow):,} บัญชี / {int(outflow['จำนวนครั้ง'].sum()):,} ครั้ง", f"{outflow['ยอดเงิน'].sum():,.2f} ฿")
    c3.metric("🔁 บัญชีเข้า-ออกทั้งสองทาง", f"{flows['both_count']:,} บัญชี")

    def top_table(table):
        view = table.sort_values('ยอดเงิน', ascending=False).head(top_n).copy()
        view.insert(0, 'ลำดับ', range(1, len(view) + 1))
        view['ยอดเงิน'] = view['ยอดเงิน'].map(lambda v: f"{v:,.2f}")
        view['จำนวนครั้ง'] = view['จำนวนครั้ง'].astype(int)
        view['เข้า-ออก'] = view['ทั้งสองทาง'].map({True: '✓', False: ''})
        return view.drop(columns=['วันแรก', 'วันสุดท้าย', 'ทั้งสองทาง', 'ชื่อบัญชีหลัก'], errors='ignore')

    tab_in, tab_out = st.tabs([f"โอนเข้า สูงสุด {top_n} อันดับ", f"โอนออก สูงสุด {top_n} อันดับ"])
    with tab_in:
        st.dataframe(top_table(inflow), use_container_width=True, hide_index=True)
    with tab_out:
        st.dataframe(top_table(outflow), use_container_width=True, hide_index=True)

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
        elif "BAY" in bank_name:
            st.info("กำลังประมวลผลข้อมูลตามโครงสร้างของธนาคารกรุงศรีอยุธยา (BAY)...")
            processed_data, df_show, warn_msg = process_bay(excel_file, main_acc_num, main_acc_name)
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

        st.success(f"ประมวลผลสำเร็จ จำนวน {len(df_show):,} รายการ")
        st.write("ตัวอย่างข้อมูลที่ประมวลผลแล้ว (5 แถวแรก):")
        display_df = df_show.drop(columns=[c for c in df_show.columns if str(c).startswith('_')])
        preview = display_df.head().copy()
        preview['วันที่ทำรายการ'] = preview['วันที่ทำรายการ'].apply(lambda v: v.strftime('%d/%m/%Y') if isinstance(v, (pd.Timestamp, datetime)) and pd.notna(v) else v)
        st.dataframe(preview, use_container_width=True, hide_index=True)

        show_flow_summary(df_show, df_show.attrs.get('main_account'), **df_show.attrs.get('flow_kwargs', {}))

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
    bank_chips = "".join(f"<span>{b.split('(')[-1].rstrip(')')}</span>" for b in BANK_PASSWORDS)
    st.markdown(f"""
    <div class="hero">
        <h1>DATA CLEANSING SYSTEM</h1>
        <p>แปลงรายการเดินบัญชีธนาคารให้อยู่ในรูปแบบมาตรฐาน พร้อมสรุปบัญชีคู่โอนขาเข้า - ขาออก (Pivot)</p>
        <div class="bank-chips">{bank_chips}</div>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("1. เลือกธนาคาร")
    selected_bank = st.selectbox("ระบุธนาคารเจ้าของไฟล์:", list(BANK_PASSWORDS.keys()))

    main_acc_num, main_acc_name = "", ""
    if "BAY" in selected_bank:
        st.info("ระบุบัญชีหลักได้ (ไม่บังคับ) หากเว้นว่าง ระบบจะใช้เลขบัญชีที่ปรากฏบ่อยที่สุดในไฟล์")
        main_acc_num = st.text_input("หมายเลขบัญชีหลัก (10 หลัก):", max_chars=10)
        main_acc_name = st.text_input("ชื่อบัญชีหลัก:")
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
