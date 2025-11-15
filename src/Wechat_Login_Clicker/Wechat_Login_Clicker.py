import win32gui
import win32con
import win32api
import time


def click_wechat_buttons():
    # 获取微信窗口
    hwnd = win32gui.FindWindow(None, "微信")
    if hwnd == 0:
        print("找不到微信登录窗口")
        return False
    
    # 获取窗口位置和大小
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    
    # 强制显示窗口并激活 - 使用多种方法确保窗口显示
    # 首先尝试恢复窗口
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    time.sleep(0.2)  # 增加等待时间
    
    # 如果窗口最小化，尝试显示窗口
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        time.sleep(0.2)
    
    # 尝试强制显示窗口
    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
    time.sleep(0.2)
    
    # 多次尝试激活窗口
    activated = False
    for _ in range(2):  # 增加尝试次数
        try:
            # 尝试使用不同的方法激活窗口
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.2)  # 增加等待时间
            
            # 验证窗口是否真的在前台
            if win32gui.GetForegroundWindow() == hwnd:
                activated = True
                break
                
            # 如果第一种方法失败，尝试另一种方法
            # 先最小化再恢复可能有助于强制前置窗口
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            time.sleep(0.2)
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.2)
        except Exception as e:
            print(f"激活窗口尝试失败: {str(e)}")
            time.sleep(0.2)
    
    if not activated:
        print("警告: 无法确认微信窗口已成功激活，但将继续尝试点击")
    
    # 移动鼠标并点击
    confirm_x = width // 2
    confirm_y = height // 2 + 50
    win32api.SetCursorPos((left + confirm_x, top + confirm_y))
    time.sleep(0.1)  # 等待鼠标移动
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.1)  # 确保点击被识别
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    
    time.sleep(0.5)  # 等待确定按钮响应
    
    # 再次确认窗口在前台
    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    except Exception as e:
        print(f"再次激活窗口失败: {str(e)}")
        pass
    
    # 点击"登录"按钮
    login_x = width // 2
    login_y = height - 90
    win32api.SetCursorPos((left + login_x, top + login_y))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    
    # 成功执行完所有步骤，返回True
    return True

if __name__ == "__main__":
    click_wechat_buttons()