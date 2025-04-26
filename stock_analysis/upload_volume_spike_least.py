import twstock
import psycopg2
from datetime import datetime
from tqdm import tqdm
import os

POSTGRES_HOST ='dpg-d068qvqli9vc73e47fk0-a'
POSTGRES_DATABASE ='stock_analysis_lmf9'
POSTGRES_USER='stock_analysis_lmf9_user'
POSTGRES_PASSWORD='cJJybzGWvRRl476obchoMw89AoPHrtLD'
POSTGRES_PORT='5432'

# 從環境變數獲取 PostgreSQL 連接資訊
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv(POSTGRES_HOST),
        database=os.getenv(POSTGRES_DATABASE),
        user=os.getenv(POSTGRES_USER),
        password=os.getenv(POSTGRES_PASSWORD),
        port=os.getenv(POSTGRES_PORT)
    )

# 讀取股票清單
def read_stock_list(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

stock_list = read_stock_list('stock_list.txt')

# 分析 + 上傳函式（僅今日）
def detect_and_upload_latest(stock_id):
    try:
        stock = twstock.Stock(stock_id)
        stock.fetch_from(2025, 4)
        name = twstock.codes[stock_id].name

        volumes = stock.capacity
        dates = stock.date
        opens = stock.open
        closes = stock.close

        if len(volumes) < 6:
            return  # 至少要有5筆前日 + 今日

        # 抓最新一筆
        avg_volume = sum(volumes[-6:-1]) / 5
        today_volume = volumes[-1]
        date_obj = dates[-1]
        is_spike = today_volume > avg_volume * 2
        date_str = date_obj.strftime('%Y-%m-%d')
        open_price = opens[-1]
        close_price = closes[-1]

        # 連接到 PostgreSQL 資料庫
        conn = get_db_connection()
        cursor = conn.cursor()

        # 使用 ON CONFLICT DO NOTHING 處理重複資料
        sql = """
            INSERT INTO volume_spike (
                stock_id, stock_name, date,
                today_volume, avg_volume_5, is_spike,
                open_price, close_price
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (stock_id, date) DO NOTHING
        """
        val = (
            stock_id, name, date_str,
            today_volume, int(avg_volume), is_spike,
            open_price, close_price
        )
        cursor.execute(sql, val)
        conn.commit()
        conn.close()
        print(f"✅ {stock_id} {date_str} 上傳 {'🚨' if is_spike else '✅'}")

    except Exception as e:
        print(f"⚠️ {stock_id} 發生錯誤：{e}")

# 執行主程式，含進度列
print(f"📅 僅上傳最新一天資料（共 {len(stock_list)} 支）")
for sid in tqdm(stock_list, desc="處理股票"):
    detect_and_upload_latest(sid)

print("✅ 上傳完成")