import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path
from asammdf import MDF
import can, csv, threading, pandas as pd
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from ttkbootstrap import Style

def convert_and_upload(in_dir, out_dir, acc_url, container, text, progress):
    in_dir, out_dir = Path(in_dir), Path(out_dir)
    client = BlobServiceClient(account_url=acc_url,
                               credential=DefaultAzureCredential()) if acc_url else None
    files = (list(in_dir.glob("*.mf4")) + list(in_dir.glob("*.MF4")) +
             list(in_dir.glob("*.blf")) + list(in_dir.glob("*.BLF")))
    if not files:
        text.insert("end", "No MF4/BLF files found\n"); text.see("end"); return
    progress.config(mode="indeterminate"); progress.start(10)
    for f in files:
        try:
            outs = []
            if f.suffix.lower() == ".mf4":
                df = MDF(f).to_dataframe()
                out = out_dir / (f.stem + ".csv")
                df.to_csv(out, index=False)
                outs.append(out)
            else:
                out = out_dir / (f.stem + ".csv")
                with open(out, "w", newline="") as g:
                    w = csv.writer(g); w.writerow(["ts","id","dlc","data"])
                    for msg in can.BLFReader(f):
                        w.writerow([msg.timestamp, hex(msg.arbitration_id),
                                    msg.dlc, msg.data.hex()])
                outs.append(out)
            msg = f"OK {f.name}"
            if client:
                for o in outs:
                    bc = client.get_blob_client(container, o.name)
                    with open(o, "rb") as fh:
                        bc.upload_blob(fh, overwrite=True)
                msg += f"  ☁️ Azure ({len(outs)} CSV)"
        except Exception as e:
            msg = f"FAIL {f.name}: {e}"
        text.insert("end", msg + "\n"); text.see("end")
    progress.stop(); progress.config(mode="determinate", value=100)

def gui():
    root = tk.Tk(); Style(theme="darkly")
    purple_bg, header_bg = "#2b143f", "#3a1f5c"
    root.title("MF4 / BLF Log Converter")
    root.geometry("1000x650"); root.minsize(1000, 650); root.configure(bg=purple_bg)
    for c in range(3): root.columnconfigure(c, weight=1)

    header = tk.Frame(root, bg=header_bg, bd=2, relief="ridge")
    header.grid(row=0, column=0, columnspan=3, sticky="ew", padx=20, pady=(20, 8))
    tk.Label(header, text="Log Converter",
             font=("Segoe UI", 20, "bold"),
             bg=header_bg, fg="white").pack(pady=(4, 0))
    tk.Label(header, text="MF4 / BLF  →  CSV  →  Azure Blob Storage",
             font=("Segoe UI", 11),
             bg=header_bg, fg="#5bc0de").pack(pady=(0, 6))

    in_var, out_var, acc_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
    cont_var = tk.StringVar(value="adas-logs")

    form = tk.Frame(root, bg=purple_bg, bd=1, relief="groove")
    form.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=20, pady=8)
    form.columnconfigure(0, weight=0, minsize=150)
    form.columnconfigure(1, weight=1)
    form.columnconfigure(2, weight=0)
    lab = lambda t,r: tk.Label(form, text=t, bg=purple_bg, fg="white",
                               font=("Segoe UI",10)).grid(row=r, column=0,
                                                          sticky="e", padx=10, pady=8)

    lab("Input folder:", 0)
    ttk.Entry(form, textvariable=in_var, width=70).grid(row=0, column=1, sticky="we", pady=8)
    ttk.Button(form, text="Browse", style="info.TButton", width=12,
               command=lambda: in_var.set(filedialog.askdirectory())
               ).grid(row=0, column=2, padx=10, pady=8)

    lab("Output folder:", 1)
    ttk.Entry(form, textvariable=out_var, width=70).grid(row=1, column=1, sticky="we", pady=8)
    ttk.Button(form, text="Browse", style="info.TButton", width=12,
               command=lambda: out_var.set(filedialog.askdirectory())
               ).grid(row=1, column=2, padx=10, pady=8)

    lab("Azure URL:", 2)
    ttk.Entry(form, textvariable=acc_var, width=70).grid(row=2, column=1,
                                                         columnspan=2, sticky="we", pady=8)

    lab("Container:", 3)
    ttk.Entry(form, textvariable=cont_var, width=25).grid(row=3, column=1,
                                                          sticky="w", pady=8)

    bottom = tk.Frame(root, bg=purple_bg)
    bottom.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=20, pady=(8, 12))
    bottom.columnconfigure(0, weight=1); bottom.rowconfigure(1, weight=1)

    ttk.Style().configure("Striped.Horizontal.TProgressbar",
                          troughcolor="#222", background="#5cb85c",
                          bordercolor="#444", lightcolor="#5bc0de",
                          darkcolor=purple_bg)
    progress = ttk.Progressbar(bottom, mode="determinate", length=900,
                               style="Striped.Horizontal.TProgressbar")
    progress.grid(row=0, column=0, sticky="ew", pady=(0, 6))

    log_frame = tk.Frame(bottom, bg=purple_bg, bd=1, relief="sunken")
    log_frame.grid(row=1, column=0, sticky="nsew")
    log = tk.Text(log_frame, height=14, width=110, bg="#222",
                  fg="white", insertbackground="white",
                  borderwidth=0, font=("Consolas", 9))
    log.pack(fill="both", expand=True)

    btn_frame = tk.Frame(root, bg=purple_bg)
    btn_frame.grid(row=3, column=0, columnspan=3, pady=(0, 20))

    def start():
        if not in_var.get() or not out_var.get(): return
        progress["value"] = 0; log.delete("1.0", "end")
        threading.Thread(target=convert_and_upload,
                         args=(in_var.get(), out_var.get(),
                               acc_var.get(), cont_var.get(),
                               log, progress),
                         daemon=True).start()

    ttk.Button(btn_frame, text="RUN CONVERSION",
               style="success.TButton", width=28,
               command=start).pack()

    root.mainloop()

if __name__ == "__main__":
    gui()
