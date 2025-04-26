from flask import Flask, render_template, request
import os
import psycopg2
from psycopg2.extras import DictCursor
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

app = Flask(__name__)

POSTGRES_HOST ='dpg-d068qvqli9vc73e47fk0-a'
POSTGRES_DATABASE ='stock_analysis_lmf9'
POSTGRES_USER='stock_analysis_lmf9_user'
POSTGRES_PASSWORD='cJJybzGWvRRl476obchoMw89AoPHrtLD'
POSTGRES_PORT='5432'

# 從環境變數獲取 PostgreSQL 連接資訊
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv(POSTGRES_HOST),
        database=os.getenv(POSTGRES_DATABASE),
        user=os.getenv(POSTGRES_USER),
        password=os.getenv(POSTGRES_PASSWORD),
        port=os.getenv(POSTGRES_PORT)
    )
    return conn

# 初始化資料庫表格
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS volume_spike (
            id SERIAL PRIMARY KEY,
            stock_id VARCHAR(10) NOT NULL,
            stock_name VARCHAR(50) NOT NULL,
            date DATE NOT NULL,
            today_volume INTEGER NOT NULL,
            avg_volume_5 INTEGER NOT NULL,
            is_spike BOOLEAN NOT NULL,
            open_price NUMERIC(10, 2),
            close_price NUMERIC(10, 2),
            UNIQUE(stock_id, date)
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

@app.route('/')
def index():
    init_db()  # 確保資料庫表格存在
    
    stock_id = request.args.get('stock_id', '').strip()
    start_date = request.args.get('start_date', '').strip()
    if not start_date:
        start_date = (datetime.today() - timedelta(days=10)).strftime('%Y-%m-%d')
    end_date = request.args.get('end_date', '').strip()
    spike_only = request.args.get('spike_only', '') == 'true'
    up_only = request.args.get('up_only', '') == 'true'

    query = "SELECT * FROM volume_spike WHERE 1=1 "
    params = []

    if stock_id:
        query += " AND stock_id = %s"
        params.append(stock_id)

    if spike_only:
        query += " AND is_spike = TRUE"

    if start_date:
        query += " AND date >= %s"
        params.append(start_date)

    if end_date:
        query += " AND date <= %s"
        params.append(end_date)

    query += " ORDER BY stock_id ASC, date DESC"

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    
    if up_only:
        rows = [r for r in rows if r['close_price'] is not None and 
               r['open_price'] is not None and 
               r['close_price'] > r['open_price']]

    cursor.execute("SELECT DISTINCT stock_id FROM volume_spike ORDER BY stock_id")
    stock_ids = [r['stock_id'] for r in cursor.fetchall()]

    cursor.close()
    conn.close()

    spike_count = sum(1 for r in rows if r['is_spike'])
    normal_count = len(rows) - spike_count

    # EPS + 合理價功能
    valuation = None
    if stock_id:
        stock_code = str(stock_id)
        eps = get_single_stock_eps(stock_code)
        
        if eps:
            result = calculate_valuation(float(eps))
            valuation = {
                "stock_id": stock_id,
                "eps": eps,
                "pe_low": 10,
                "pe_mid": 15,
                "pe_high": 20,
                "cheap_price": result["便宜價"],
                "fair_price": result["合理價"],
                "expensive_price": result["昂貴價"]
            }

    return render_template('index.html',
                         stocks=rows,
                         stock_id=stock_id,
                         stock_ids=stock_ids,
                         spike_only=spike_only,
                         up_only=up_only,
                         start_date=start_date,
                         end_date=end_date,
                         spike_count=spike_count,
                         normal_count=normal_count,
                         valuation=valuation)

def get_single_stock_eps(stock_code):
    url = f"https://openapi.twse.com.tw/v1/opendata/t187ap14_L"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        for item in data:
            if item['公司代號'] == stock_code:
                return item['基本每股盈餘(元)']
    return None

def calculate_valuation(eps, pe_low=10, pe_mid=15, pe_high=20):
    return {
        "便宜價": round(eps * pe_low, 2),
        "合理價": round(eps * pe_mid, 2),
        "昂貴價": round(eps * pe_high, 2)
    }

if __name__ == '__main__':
    init_db()
    app.run(debug=True)