"""Windows desktop control window. Phone mode shares the same local build service."""
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from server import start_server

def main():
    window = tk.Tk()
    window.title('QuoteCraft APK Builder')
    window.geometry('610x470')
    window.configure(bg='#f5f1e8')
    frame = ttk.Frame(window, padding=28)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='QuoteCraft APK Builder', font=('Segoe UI', 22, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='Choose an HTML file. Build an Android app.', font=('Segoe UI', 12)).pack(anchor='w', pady=(8,24))
    phone = tk.BooleanVar(value=False)
    phone_toggle = ttk.Checkbutton(frame, text='Allow my Android phone to use this builder on the same Wi-Fi', variable=phone)
    phone_toggle.pack(anchor='w')
    server = None
    url = None
    text = tk.Text(frame, height=10, wrap='word', font=('Segoe UI', 11), relief='flat')
    text.pack(fill='both', expand=True, pady=16)
    text.insert('1.0', '1. Install the one-time build tools listed in START-HERE.md.\n\n2. Click Open Builder below.\n\n3. Choose your HTML or ZIP, enter an app name, then click Build APK.\n\nYour APKs and signing keys remain on this computer.')
    text.configure(state='disabled')
    def open_builder():
        nonlocal server, url
        if server:
            webbrowser.open(url)
            return
        try:
            server, token, hosts = start_server(phone.get())
            url = 'http://127.0.0.1:8765/#' + token
            threading.Thread(target=server.serve_forever, daemon=True).start()
            phone_toggle.configure(state='disabled')
            details = 'The builder is running. Keep this window open.\n\nPairing code:\n' + token
            if phone.get():
                addresses = hosts - {'127.0.0.1','localhost'}
                details += '\n\nOn your Android phone, open Chrome and enter:\n' + '\n'.join('http://' + host + ':8765' for host in sorted(addresses))
                details += '\n\nEnter the pairing code above. Both devices need the same trusted Wi-Fi. If Windows asks, allow Private networks.'
            text.configure(state='normal'); text.delete('1.0','end'); text.insert('1.0', details); text.configure(state='disabled')
            webbrowser.open(url)
        except OSError as e:
            server = None
            messagebox.showerror('Could not start builder', str(e) + '\nClose another running builder and try again.')
    ttk.Button(frame, text='Open Builder', command=open_builder).pack(fill='x', ipady=8)
    def close():
        if server: server.shutdown(); server.server_close()
        window.destroy()
    window.protocol('WM_DELETE_WINDOW', close)
    window.mainloop()

if __name__ == '__main__': main()
