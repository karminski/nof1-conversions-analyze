import requests
import json
import time
import os
from datetime import datetime

# 配置
API_URL = "https://nof1.ai/api/conversations"
SAVE_DIR = "conversions"
FETCH_INTERVAL = 15  # 秒


def create_save_directory():
    """创建保存目录"""
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
        print(f"✓ 已创建目录: {SAVE_DIR}")


def fetch_data():
    """获取API数据"""
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


def save_data(data, fetch_count):
    """保存数据到文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"conversations_{timestamp}_#{fetch_count}.json"
    filepath = os.path.join(SAVE_DIR, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath, None
    except Exception as e:
        return None, str(e)


def main():
    """主函数"""
    print("=" * 60)
    print("Nof1 Conversations 数据获取脚本")
    print("=" * 60)
    print(f"API地址: {API_URL}")
    print(f"保存目录: {SAVE_DIR}")
    print(f"获取间隔: {FETCH_INTERVAL}秒")
    print("=" * 60)
    print("按 Ctrl+C 停止运行\n")

    # 创建保存目录
    create_save_directory()

    fetch_count = 0

    try:
        while True:
            fetch_count += 1
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print(f"\n[{current_time}] 第 {fetch_count} 次获取...")

            # 获取数据
            data, error = fetch_data()

            if error:
                print(f"✗ 获取失败: {error}")
            else:
                # 保存数据
                filepath, save_error = save_data(data, fetch_count)

                if save_error:
                    print(f"✗ 保存失败: {save_error}")
                else:
                    # 显示数据信息
                    conversations_count = len(data.get("conversations", []))
                    print(f"✓ 获取成功: {conversations_count} 条会话记录")
                    print(f"✓ 已保存到: {filepath}")

            # 等待下一次获取
            if fetch_count == 1:
                print(f"\n等待 {FETCH_INTERVAL} 秒后进行下一次获取...")
            else:
                print(f"等待 {FETCH_INTERVAL} 秒...")

            time.sleep(FETCH_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print(f"程序已停止")
        print(f"总共获取了 {fetch_count} 次数据")
        print(f"数据保存在: {os.path.abspath(SAVE_DIR)}")
        print("=" * 60)


if __name__ == "__main__":
    main()
