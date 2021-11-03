import socket
from threading import Thread
from tkinter import *
from tkinter.font import Font
from time import sleep
from datetime import datetime
from keyboard import *


def read_logins(filename: str):
    with open(filename, "a") as file:
        try:
            for row in file:
                login = row.split(":")[0]
                password = row.split(":")[1]
                Server.logins[login] = password
        except:
            pass


def add_login(filename: str, login: str, password: str):
    with open(filename, "a") as file:
        file.write(login + ":" + password + "\n")


def write_log(filename: str, log: str):
    with open(filename, "a") as file:
        file.write(f"{datetime.now()}:\n{log}\n\n")


def logs_generator(filename: str):
    with open(filename, "r") as file:
        for row in file:
            yield row


def clear_file(filename: str):
    open(filename, "w").close()


class Server:
    LOGINS: str = "logins.txt"
    LOG: str = "log.txt"
    BUTTON: str = "enter"
    paused_ports: list = []
    users: dict = dict()
    logins: dict = dict()

    def __init__(self):
        self.socket: socket = self.open_socket()
        self.window: Tk = Tk()
        self.text_field: Text = Text(self.window)
        self.input_field: Entry = Entry(self.window)
        self.is_focused: BooleanVar = BooleanVar()
        self.configure_window()

        self.commands: dict = {
            "exit": self.exit,
            "pause": self.pause,
            "readlogs": self.read_logs,
            "cllogs": self.clear_logs,
            "cllogins": self.clear_logins
        }

        self.accept_thread: Thread = Thread(name="accept", target=self.accept, daemon=True)
        self.console_thread: Thread = Thread(name="console", target=self.console, daemon=True)
        self.accept_thread.start()
        self.console_thread.start()
        self.threads: list = []
        self.window.mainloop()

    @staticmethod
    def open_socket() -> socket:
        sock: socket = socket.socket()
        try:
            sock.bind(("127.0.0.1", 9091))
            sock.listen(2)
        except:
            sock.close()
            raise Exception("Не получается запустить сервер")
        return sock

    def configure_window(self):
        self.window.title("Сервер")
        self.window.configure(bg="#000080")
        self.window.geometry("500x500")
        self.window.resizable(0, 0)
        self.window.bind('<FocusIn>', lambda _: self.is_focused.set(True))
        self.window.bind('<FocusOut>', lambda _: self.is_focused.set(False))

        self.text_field.configure(font=Font(size=9, weight="bold"), bg="#F5F5F5", fg="#000000", width=400, height=25)
        self.text_field.pack(side=TOP, padx=10, pady=10)

        self.input_field.configure(font=Font(size=9, weight="bold"), bg="#F5F5F5", fg="#000000", width=400)
        self.input_field.pack(side=TOP, padx=10, pady=10)
        self.input_field.focus_set()

    def accept(self):
        while True:
            try:
                accept: tuple = self.socket.accept()
                conn: socket.socket = accept[0]
                addr: tuple = accept[1]
                write_log(Server.LOG, f"Установлено соединение с {addr[0]}, {addr[1]}")
                self.threads.append(
                    Thread(name=f"{conn};{addr}", target=self.request_login, args=[conn, addr, ], daemon=True).start())
            except:
                continue

    def request_login(self, conn: socket.socket, addr: tuple):
        conn.send("Введите логин:".encode())
        login: str = conn.recv(2048).decode()

        write_log(Server.LOG, f"{addr[0]}, {addr[1]} ввел логин {login}")

        if login in Server.logins.keys():
            self.request_password(conn, addr, login)
        else:
            self.request_new_password(conn, addr, login)

    def request_new_password(self, conn: socket.socket, addr: tuple, login: str):
        conn.send("Задайте пароль:".encode())
        password: str = conn.recv(2048).decode()

        write_log(Server.LOG, f"{addr[0]}, {addr[1]} задал пароль {password}")

        Server.logins[login] = password
        conn.send("Вход выполнен".encode())

        write_log(Server.LOG, f"{addr[0]}, {addr[1]} успешно подсоединился к чату")

        add_login(Server.LOGINS, login, password)
        Server.users[conn] = login
        self.accept_and_send(conn, addr)

    def request_password(self, conn: socket.socket, addr: tuple, login: str):
        conn.send("Введите пароль:".encode())
        password: str = conn.recv(2048).decode()

        write_log(Server.LOG, f"{addr[0]}, {addr[1]} ввел пароль {password}")

        if password == Server.logins[login]:
            conn.send("Вход выполнен".encode())

            write_log(Server.LOG, f"{addr[0]}, {addr[1]} успешно подсоединился к чату")

            Server.users[conn] = login
            self.accept_and_send(conn, addr)
        else:
            self.request_password(conn, addr, login)

    def accept_and_send(self, conn: socket.socket, addr: tuple):
        while True:
            if addr[1] not in self.paused_ports:
                try:
                    data: bytes = conn.recv(2048)

                    write_log(Server.LOG, f"{addr[0]}, {addr[1]} прислал сообщение:\n{data.decode()}\n")

                    self.send_all(data, Server.users[conn])
                except ConnectionResetError:
                    Server.users.pop(conn)
                    break

    @staticmethod
    def send_all(message: bytes, user: str):
        for conn in Server.users.keys():
            try:
                conn.send(f"{user}:\n{message.decode()}".encode())
            except:
                print(conn, " не работает")

    def console(self):
        while True:
            if is_pressed(self.BUTTON) and self.is_focused.get():
                try:
                    command: str = self.input_field.get()
                    self.input_field.delete(0, END)
                    if command != "":
                        if " " in command:
                            arg: int = int(command.split(" ")[1])
                            command: str = command.split(" ")[0]
                            self.text_field.insert(END, command + " " + str(arg) + "\n")
                            self.commands[command](arg)
                        else:
                            self.text_field.insert(END, command + "\n")
                            self.commands[command]()
                except:
                    self.text_field.insert(END, "Команда не найдена\n")
                finally:
                    self.text_field.see(END)
                    sleep(0.5)

    def exit(self):
        self.socket.close()
        self.window.quit()

    def pause(self, port: str):
        self.paused_ports.append(port)

    def read_logs(self):
        for row in logs_generator(Server.LOG):
            self.text_field.insert(END, row)
        self.text_field.see(END)

    @staticmethod
    def clear_logs():
        clear_file(Server.LOG)

    @staticmethod
    def clear_logins():
        clear_file(Server.LOGINS)


def main():
    read_logins(Server.LOGINS)
    Server()


if __name__ == '__main__':
    main()