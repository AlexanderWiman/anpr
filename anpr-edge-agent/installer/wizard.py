#!/usr/bin/env python3
"""Graphical installer wizard for ANPR edge agent."""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from installer.engine import InstallConfig, check_prerequisites, run_install
from installer.sites import DEFAULT_BACKEND_URL, SITES


class InstallerWizard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ANPR — Installation")
        self.geometry("520x560")
        self.resizable(False, False)

        self._build_ui()
        self._check_prereqs()

    def _build_ui(self) -> None:
        pad = {"padx": 16, "pady": 6}
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="ANPR Edge Agent",
            font=("Helvetica", 18, "bold"),
        ).pack(anchor=tk.W, pady=(0, 4))
        ttk.Label(
            frame,
            text="Fyll i uppgifterna nedan. Programmet installeras och startar automatiskt.",
            wraplength=460,
        ).pack(anchor=tk.W, pady=(0, 12))

        ttk.Label(frame, text="Anläggning").pack(anchor=tk.W)
        self.site_var = tk.StringVar(value=SITES[0][1])
        site_combo = ttk.Combobox(
            frame,
            textvariable=self.site_var,
            values=[label for _, label in SITES],
            state="readonly",
        )
        site_combo.pack(fill=tk.X, **pad)

        ttk.Label(frame, text="Kamera-IP (t.ex. 192.168.0.96)").pack(anchor=tk.W)
        self.ip_var = tk.StringVar(value="192.168.0.96")
        ttk.Entry(frame, textvariable=self.ip_var).pack(fill=tk.X, **pad)

        ttk.Label(frame, text="Kameratyp").pack(anchor=tk.W)
        self.cam_type_var = tk.StringVar(value="ip_webcam")
        type_row = ttk.Frame(frame)
        type_row.pack(fill=tk.X, **pad)
        ttk.Radiobutton(
            type_row, text="IP Webcam (HTTP)", variable=self.cam_type_var, value="ip_webcam",
            command=self._on_cam_type_change,
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            type_row, text="RTSP (IP-kamera)", variable=self.cam_type_var, value="rtsp",
            command=self._on_cam_type_change,
        ).pack(side=tk.LEFT, padx=(12, 0))

        port_row = ttk.Frame(frame)
        port_row.pack(fill=tk.X, **pad)
        ttk.Label(port_row, text="Port").pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value="8080")
        ttk.Entry(port_row, textvariable=self.port_var, width=8).pack(side=tk.LEFT, padx=8)

        self.rtsp_frame = ttk.LabelFrame(frame, text="RTSP (valfritt)", padding=8)
        self.rtsp_frame.pack(fill=tk.X, **pad)
        ttk.Label(self.rtsp_frame, text="Sökväg").grid(row=0, column=0, sticky=tk.W)
        self.rtsp_path_var = tk.StringVar(value="/stream1")
        ttk.Entry(self.rtsp_frame, textvariable=self.rtsp_path_var).grid(row=0, column=1, sticky=tk.EW, padx=8)
        ttk.Label(self.rtsp_frame, text="Användare").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.rtsp_user_var = tk.StringVar()
        ttk.Entry(self.rtsp_frame, textvariable=self.rtsp_user_var).grid(row=1, column=1, sticky=tk.EW, padx=8)
        ttk.Label(self.rtsp_frame, text="Lösenord").grid(row=2, column=0, sticky=tk.W)
        self.rtsp_pass_var = tk.StringVar()
        ttk.Entry(self.rtsp_frame, textvariable=self.rtsp_pass_var, show="•").grid(row=2, column=1, sticky=tk.EW, padx=8)
        self.rtsp_frame.columnconfigure(1, weight=1)
        self.rtsp_frame.pack_forget()

        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, **pad)
        ttk.Label(row2, text="Kamera-ID").grid(row=0, column=0, sticky=tk.W)
        self.camera_id_var = tk.StringVar(value="entrance-1")
        ttk.Entry(row2, textvariable=self.camera_id_var, width=16).grid(row=0, column=1, sticky=tk.W, padx=8)
        ttk.Label(row2, text="Riktning").grid(row=0, column=2, sticky=tk.W, padx=(16, 0))
        self.direction_var = tk.StringVar(value="entry")
        ttk.Combobox(
            row2,
            textvariable=self.direction_var,
            values=["entry", "exit"],
            width=10,
            state="readonly",
        ).grid(row=0, column=3, sticky=tk.W)

        ttk.Label(frame, text="Backend-token (från IT)").pack(anchor=tk.W)
        self.token_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.token_var, show="•").pack(fill=tk.X, **pad)

        self.backend_var = tk.StringVar(value=DEFAULT_BACKEND_URL)
        ttk.Label(frame, text="Backend-URL (ändra bara om IT säger till)").pack(anchor=tk.W)
        ttk.Entry(frame, textvariable=self.backend_var).pack(fill=tk.X, **pad)

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(12, 4))

        self.status = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.status, wraplength=460).pack(anchor=tk.W)

        self.install_btn = ttk.Button(
            frame, text="Installera och starta", command=self._on_install
        )
        self.install_btn.pack(pady=12, ipadx=12, ipady=4)

    def _on_cam_type_change(self) -> None:
        if self.cam_type_var.get() == "rtsp":
            self.port_var.set("554")
            self.rtsp_frame.pack(fill=tk.X, padx=16, pady=6)
        else:
            self.port_var.set("8080")
            self.rtsp_frame.pack_forget()

    def _check_prereqs(self) -> None:
        issues = check_prerequisites()
        if issues:
            messagebox.showwarning(
                "Kontrollera innan installation",
                "\n\n".join(issues),
            )

    def _site_id(self) -> str:
        label = self.site_var.get()
        for site_id, site_label in SITES:
            if site_label == label:
                return site_id
        return "falun"

    def _validate(self) -> InstallConfig | None:
        ip = self.ip_var.get().strip()
        token = self.token_var.get().strip()
        if not ip:
            messagebox.showerror("Saknas", "Ange kamera-IP.")
            return None
        if not token or token == "change-me":
            messagebox.showerror("Saknas", "Ange backend-token från IT.")
            return None
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Fel", "Port måste vara ett tal.")
            return None

        return InstallConfig(
            site_id=self._site_id(),
            camera_ip=ip,
            camera_type=self.cam_type_var.get(),
            camera_port=port,
            rtsp_path=self.rtsp_path_var.get().strip(),
            rtsp_user=self.rtsp_user_var.get().strip(),
            rtsp_password=self.rtsp_pass_var.get(),
            camera_id=self.camera_id_var.get().strip() or "entrance-1",
            direction=self.direction_var.get(),
            backend_url=self.backend_var.get().strip(),
            anpr_token=token,
        )

    def _log(self, msg: str) -> None:
        self.status.set(msg)
        self.update_idletasks()

    def _on_install(self) -> None:
        cfg = self._validate()
        if cfg is None:
            return

        if not messagebox.askyesno(
            "Bekräfta",
            f"Installera för {self.site_var.get()}?\n\nKamera: {cfg.camera_ip}\n\nDet kan ta några minuter första gången.",
        ):
            return

        self.install_btn.config(state=tk.DISABLED)
        self.progress.start(12)

        def work() -> None:
            try:
                run_install(cfg, self._log)
                self.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Klart!",
                        "ANPR är installerat och körs.\n\n"
                        "Webbläsaren öppnas automatiskt.\n"
                        "Använd genvägen 'ANPR' på skrivbordet senare.\n\n"
                        "Systemet startar själv vid omstart av datorn.",
                    ),
                )
            except Exception as exc:
                self.after(
                    0,
                    lambda: messagebox.showerror("Installation misslyckades", str(exc)),
                )
            finally:
                self.after(0, self._install_done)

        threading.Thread(target=work, daemon=True).start()

    def _install_done(self) -> None:
        self.progress.stop()
        self.install_btn.config(state=tk.NORMAL)


def main() -> None:
    try:
        app = InstallerWizard()
        app.mainloop()
    except tk.TclError as exc:
        print(f"GUI not available: {exc}")
        print("Run: python3 installer/cli.py")
        sys.exit(1)


if __name__ == "__main__":
    main()
