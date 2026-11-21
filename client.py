import tkinter as tk
from tkinter import messagebox, simpledialog
import requests

SERVER_URL = "http://127.0.0.1:8000"

class RPGClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Text RPG Online (MS SQL)")
        self.root.geometry("720x540")
        self.token = None
        self.locations = []

        self.build_ui()
        self.auth_flow()

    def build_ui(self):
        self.stats_label = tk.Label(self.root, text="Загрузка...", font=("Arial", 11, "bold"))
        self.stats_label.pack(pady=5)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Искать приключения", command=lambda: self.send_action("explore")).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Отдохнуть (+30 HP)", command=lambda: self.send_action("heal")).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Сменить локацию", command=self.change_location).pack(side=tk.LEFT, padx=5)

        self.log_text = tk.Text(self.root, height=12, state="disabled")
        self.log_text.pack(fill=tk.X, padx=10, pady=5)

        info_frame = tk.Frame(self.root)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        self.online_label = tk.Label(info_frame, text="В сети:\n-", justify=tk.LEFT, anchor="nw", width=22, relief="groove")
        self.online_label.pack(side=tk.LEFT, fill=tk.Y, padx=2)

        self.leaders_label = tk.Label(info_frame, text="Лидеры:\n-", justify=tk.LEFT, anchor="nw", width=22, relief="groove")
        self.leaders_label.pack(side=tk.LEFT, fill=tk.Y, padx=2)

        self.inv_label = tk.Label(info_frame, text="Инвентарь:\n-", justify=tk.LEFT, anchor="nw", width=30, relief="groove")
        self.inv_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        interact_frame = tk.Frame(self.root)
        interact_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(interact_frame, text="Чат:").pack(side=tk.LEFT)
        self.chat_entry = tk.Entry(interact_frame, width=32)
        self.chat_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(interact_frame, text="Отправить", command=self.send_chat).pack(side=tk.LEFT)
        tk.Button(interact_frame, text="Передать предмет", command=self.transfer_item).pack(side=tk.RIGHT)

    def append_log(self, text):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def auth_flow(self):
        is_new = messagebox.askyesno("Авторизация", "У вас уже есть аккаунт?\n(Нажмите 'Нет', чтобы зарегистрироваться)")
        username = simpledialog.askstring("Авторизация", "Введите логин:", parent=self.root)
        if not username:
            self.root.destroy()
            return
        password = simpledialog.askstring("Авторизация", "Введите пароль:", show="*", parent=self.root)
        if not password:
            self.root.destroy()
            return

        try:
            # Если аккаунта нет — сначала регистрируем
            if not is_new:
                reg_res = requests.post(f"{SERVER_URL}/register", json={"username": username, "password": password}, timeout=5)
                if reg_res.status_code != 200:
                    messagebox.showerror("Ошибка регистрации", reg_res.json().get("detail", "Ошибка сервера"))
                    self.root.destroy()
                    return
                messagebox.showinfo("Успех", "Регистрация прошла успешно! Выполняется вход...")

            # Выполняем вход и получаем токен сессии
            res = requests.post(f"{SERVER_URL}/login", json={"username": username, "password": password}, timeout=5)
            if res.status_code != 200:
                messagebox.showerror("Ошибка входа", res.json().get("detail", "Неверный логин или пароль"))
                self.root.destroy()
                return

            self.token = res.json()["token"]
            self.append_log(f"Добро пожаловать, {username}!")
            self.refresh_state()
        except Exception as e:
            messagebox.showerror("Ошибка сети", f"Не удалось подключиться к серверу: {e}")
            self.root.destroy()

    def send_action(self, action, location_id=1):
        try:
            res = requests.post(f"{SERVER_URL}/action", json={"token": self.token, "action": action, "location_id": location_id}, timeout=5)
            if res.status_code == 200:
                self.append_log(res.json()["message"])
                self.refresh_state()
            else:
                messagebox.showwarning("Внимание", res.json().get("detail", "Ошибка"))
        except Exception as e:
            self.append_log(f"Ошибка сети: {e}")

    def change_location(self):
        if not self.locations:
            return
        loc_list = "\n".join([f"{l['id']} - {l['name']}" for l in self.locations])
        loc_id = simpledialog.askinteger("Перемещение", f"Введите ID локации:\n{loc_list}", parent=self.root)
        if loc_id:
            self.send_action("move", location_id=loc_id)

    def send_chat(self):
        msg = self.chat_entry.get().strip()
        if not msg:
            return
        try:
            requests.post(f"{SERVER_URL}/interact", json={"token": self.token, "chat_text": msg}, timeout=5)
            self.chat_entry.delete(0, tk.END)
            self.refresh_state()
        except Exception as e:
            self.append_log(f"Ошибка отправки: {e}")

    def transfer_item(self):
        target = simpledialog.askstring("Обмен", "Имя персонажа получателя:", parent=self.root)
        if not target:
            return
        item_name = simpledialog.askstring("Обмен", "Точное название предмета из инвентаря:", parent=self.root)
        if not item_name:
            return
        try:
            res = requests.post(f"{SERVER_URL}/interact", json={"token": self.token, "recipient_char": target, "item_name": item_name}, timeout=5)
            if res.status_code == 200:
                self.append_log(f"Предмет '{item_name}' передан игроку {target}.")
                self.refresh_state()
            else:
                messagebox.showwarning("Ошибка", res.json().get("detail", "Не удалось передать"))
        except Exception as e:
            self.append_log(f"Ошибка сети: {e}")

    def refresh_state(self):
        if not self.token:
            return
        try:
            res = requests.get(f"{SERVER_URL}/state/{self.token}", timeout=5)
            if res.status_code == 200:
                data = res.json()
                p = data["player"]
                self.locations = data["locations"]
                self.stats_label.config(text=f"Персонаж: {p['username']} | Локация: {p['location']} | HP: {p['hp']} | Уровень: {p['level']}")
                self.online_label.config(text="В сети:\n" + "\n".join(data["online_players"]))
                self.leaders_label.config(text="Лидеры:\n" + "\n".join([f"{l['username']} ({l['score']})" for l in data["leaderboard"]]))
                self.inv_label.config(text="Инвентарь:\n" + "\n".join([f"- {i['name']} (x{i['count']})" for i in p["inventory"]]))

                if data["logs"]:
                    last_msg = data["logs"][-1]
                    if last_msg not in self.log_text.get("1.0", tk.END):
                        self.append_log(last_msg)
        except Exception:
            pass
        self.root.after(3000, self.refresh_state)

if __name__ == "__main__":
    root = tk.Tk()
    app = RPGClient(root)
    root.mainloop()
